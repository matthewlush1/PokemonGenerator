"""
Wasserstein GAN with Gradient Penalty (WGAN-GP) for sharp pixel art generation.

Architecture:
  - Generator: ConvTranspose2d (no Batch Norm in last layer) -> Tanh [-1, 1]
  - Discriminator (Critic): Conv2d with InstanceNorm (crucial for WGAN-GP) -> Score
  - Loss: Wasserstein distance with Gradient Penalty constraint
"""

import torch
import torch.nn as nn
from ml.sprite_dataset import COND_DIM

LATENT_DIM = 128
IMG_SIZE = 64
IMG_CHANNELS = 4  # RGBA


class Generator(nn.Module):
    """Generator: Z + Condition -> Image (64x64)"""
    def __init__(self, latent_dim=LATENT_DIM, cond_dim=COND_DIM):
        super().__init__()
        
        # Initial projection: 128 + 56 -> 256*4*4
        self.fc = nn.Sequential(
            nn.Linear(latent_dim + cond_dim, 256 * 4 * 4),
            nn.LeakyReLU(0.2, inplace=True)
        )

        # 4x4 -> 8x8 -> 16x16 -> 32x32 -> 64x64
        self.conv_blocks = nn.Sequential(
            # 4x4 -> 8x8
            nn.ConvTranspose2d(256, 128, 4, 2, 1),
            nn.BatchNorm2d(128),
            nn.LeakyReLU(0.2, inplace=True),

            # 8x8 -> 16x16
            nn.ConvTranspose2d(128, 64, 4, 2, 1),
            nn.BatchNorm2d(64),
            nn.LeakyReLU(0.2, inplace=True),

            # 16x16 -> 32x32
            nn.ConvTranspose2d(64, 32, 4, 2, 1),
            nn.BatchNorm2d(32),
            nn.LeakyReLU(0.2, inplace=True),

            # 32x32 -> 64x64
            nn.ConvTranspose2d(32, IMG_CHANNELS, 4, 2, 1),
            nn.Tanh()  # Output range [-1, 1]
        )

    def forward(self, z, cond):
        x = torch.cat([z, cond], dim=1)
        x = self.fc(x)
        x = x.view(-1, 256, 4, 4)
        img = self.conv_blocks(x)
        return img


class Discriminator(nn.Module):
    """Discriminator (Critic): Image + Condition -> Realness Score"""
    def __init__(self, cond_dim=COND_DIM):
        super().__init__()
        
        # Image Feature Extractor: 64x64 -> ... -> 4x4
        self.image_conv = nn.Sequential(
            # 64x64 -> 32x32
            nn.Conv2d(IMG_CHANNELS, 32, 4, 2, 1),
            nn.LeakyReLU(0.2, inplace=True),
            # NO Batch Norm in first layer or WGAN constraint breaks

            # 32x32 -> 16x16
            nn.Conv2d(32, 64, 4, 2, 1),
            nn.InstanceNorm2d(64, affine=True),  # Instance Norm for WGAN-GP
            nn.LeakyReLU(0.2, inplace=True),

            # 16x16 -> 8x8
            nn.Conv2d(64, 128, 4, 2, 1),
            nn.InstanceNorm2d(128, affine=True),
            nn.LeakyReLU(0.2, inplace=True),

            # 8x8 -> 4x4
            nn.Conv2d(128, 256, 4, 2, 1),
            nn.InstanceNorm2d(256, affine=True),
            nn.LeakyReLU(0.2, inplace=True),
        )

        # Condition Feature Extractor
        self.cond_fc = nn.Sequential(
            nn.Linear(cond_dim, 64),
            nn.LeakyReLU(0.2, inplace=True)
        )

        # Combined Scorer
        # Image feats: 256*4*4 = 4096. Condition feats: 64.
        self.final_score = nn.Linear(256 * 4 * 4 + 64, 1)

    def forward(self, img, cond):
        img_feats = self.image_conv(img)
        img_feats = img_feats.view(img_feats.size(0), -1)  # Flatten

        cond_feats = self.cond_fc(cond)

        combined = torch.cat([img_feats, cond_feats], dim=1)
        score = self.final_score(combined)
        return score  # No Sigmoid! Wasserstein distance is unbounded.


def compute_gradient_penalty(D, real_samples, fake_samples, cond, device):
    """Calculates the gradient penalty loss for WGAN-GP."""
    # Random weight term for interpolation between real and fake samples
    alpha = torch.rand(real_samples.size(0), 1, 1, 1, device=device)
    
    # Get random interpolation between real and fake samples
    interpolates = (alpha * real_samples + ((1 - alpha) * fake_samples)).requires_grad_(True)
    
    # Get discriminator output for interpolates
    d_interpolates = D(interpolates, cond)
    
    # Get gradients w.r.t. interpolates
    fake = torch.ones(real_samples.size(0), 1, device=device, requires_grad=False)
    gradients = torch.autograd.grad(
        outputs=d_interpolates,
        inputs=interpolates,
        grad_outputs=fake,
        create_graph=True,
        retain_graph=True,
        only_inputs=True,
    )[0]
    
    gradients = gradients.view(gradients.size(0), -1)
    gradient_penalty = ((gradients.norm(2, dim=1) - 1) ** 2).mean()
    return gradient_penalty
