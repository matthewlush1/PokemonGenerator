"""
Conditional VAE (CVAE) model for Pokémon sprite generation.

Architecture:
  - Encoder: Conv2d(4→32→64→128→256) + condition → μ, log_σ²
  - Decoder: FC(latent+cond) → reshape → ConvTranspose2d → 64×64×4 RGBA
  - Latent dim: 128, conditioning dim: 56
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from ml.sprite_dataset import COND_DIM


LATENT_DIM = 128
IMG_SIZE = 64
IMG_CHANNELS = 4  # RGBA


class Encoder(nn.Module):
    """Convolutional encoder: image + condition → μ, log_var."""

    def __init__(self, latent_dim=LATENT_DIM, cond_dim=COND_DIM):
        super().__init__()
        self.cond_dim = cond_dim

        # Conv layers: 64→32→16→8→4
        self.conv = nn.Sequential(
            nn.Conv2d(IMG_CHANNELS, 32, 4, 2, 1),   # 64→32
            nn.BatchNorm2d(32),
            nn.LeakyReLU(0.2),

            nn.Conv2d(32, 64, 4, 2, 1),              # 32→16
            nn.BatchNorm2d(64),
            nn.LeakyReLU(0.2),

            nn.Conv2d(64, 128, 4, 2, 1),             # 16→8
            nn.BatchNorm2d(128),
            nn.LeakyReLU(0.2),

            nn.Conv2d(128, 256, 4, 2, 1),            # 8→4
            nn.BatchNorm2d(256),
            nn.LeakyReLU(0.2),
        )
        # 256 * 4 * 4 = 4096
        flat_dim = 256 * 4 * 4
        fc_in = flat_dim + cond_dim

        self.fc_mu = nn.Linear(fc_in, latent_dim)
        self.fc_logvar = nn.Linear(fc_in, latent_dim)

    def forward(self, x, cond):
        h = self.conv(x)
        h = h.view(h.size(0), -1)                   # Flatten
        h = torch.cat([h, cond], dim=1)              # Concat condition
        mu = self.fc_mu(h)
        logvar = self.fc_logvar(h)
        return mu, logvar


class Decoder(nn.Module):
    """Deconvolutional decoder: z + condition → image."""

    def __init__(self, latent_dim=LATENT_DIM, cond_dim=COND_DIM):
        super().__init__()

        fc_out = 256 * 4 * 4
        self.fc = nn.Sequential(
            nn.Linear(latent_dim + cond_dim, fc_out),
            nn.LeakyReLU(0.2),
        )

        # Deconv layers: 4→8→16→32→64
        self.deconv = nn.Sequential(
            nn.ConvTranspose2d(256, 128, 4, 2, 1),   # 4→8
            nn.BatchNorm2d(128),
            nn.LeakyReLU(0.2),

            nn.ConvTranspose2d(128, 64, 4, 2, 1),    # 8→16
            nn.BatchNorm2d(64),
            nn.LeakyReLU(0.2),

            nn.ConvTranspose2d(64, 32, 4, 2, 1),     # 16→32
            nn.BatchNorm2d(32),
            nn.LeakyReLU(0.2),

            nn.ConvTranspose2d(32, IMG_CHANNELS, 4, 2, 1),  # 32→64
            nn.Sigmoid(),  # Output [0, 1]
        )

    def forward(self, z, cond):
        h = torch.cat([z, cond], dim=1)
        h = self.fc(h)
        h = h.view(-1, 256, 4, 4)
        return self.deconv(h)


class ConditionalVAE(nn.Module):
    """Full Conditional VAE: encode → reparameterize → decode."""

    def __init__(self, latent_dim=LATENT_DIM, cond_dim=COND_DIM):
        super().__init__()
        self.latent_dim = latent_dim
        self.cond_dim = cond_dim
        self.encoder = Encoder(latent_dim, cond_dim)
        self.decoder = Decoder(latent_dim, cond_dim)

    def reparameterize(self, mu, logvar):
        """Reparameterization trick: z = μ + σ * ε."""
        std = torch.exp(0.5 * logvar)
        eps = torch.randn_like(std)
        return mu + eps * std

    def forward(self, x, cond):
        mu, logvar = self.encoder(x, cond)
        z = self.reparameterize(mu, logvar)
        recon = self.decoder(z, cond)
        return recon, mu, logvar

    def generate(self, cond, device="cpu", num_samples=1):
        """Generate new sprites from conditioning vectors."""
        self.eval()
        with torch.no_grad():
            if cond.dim() == 1:
                cond = cond.unsqueeze(0).repeat(num_samples, 1)
            z = torch.randn(cond.size(0), self.latent_dim).to(device)
            cond = cond.to(device)
            return self.decoder(z, cond)

    def interpolate(self, cond1, cond2, steps=10, device="cpu"):
        """Interpolate between two conditioning vectors in latent space."""
        self.eval()
        with torch.no_grad():
            results = []
            for t in torch.linspace(0, 1, steps):
                cond_interp = (1 - t) * cond1 + t * cond2
                z = torch.randn(1, self.latent_dim).to(device)
                cond_t = cond_interp.unsqueeze(0).to(device)
                img = self.decoder(z, cond_t)
                results.append(img)
            return torch.cat(results, dim=0)


def vae_loss(recon, target, mu, logvar, kl_weight=0.5):
    """CVAE loss: reconstruction (MSE) + KL divergence.

    Args:
        recon: reconstructed image [B, 4, 64, 64]
        target: original image [B, 4, 64, 64]
        mu: latent mean
        logvar: latent log variance
        kl_weight: weight for KL term (annealed during training)
    """
    # Reconstruction loss — MSE weighted by alpha channel
    alpha = target[:, 3:4, :, :]  # [B, 1, H, W]
    recon_loss = F.mse_loss(recon * alpha, target * alpha, reduction="mean")

    # Also penalize alpha reconstruction
    alpha_loss = F.mse_loss(recon[:, 3:4], target[:, 3:4], reduction="mean")

    # KL divergence
    kl_loss = -0.5 * torch.mean(1 + logvar - mu.pow(2) - logvar.exp())

    return recon_loss + alpha_loss * 0.5 + kl_weight * kl_loss, {
        "recon": recon_loss.item(),
        "alpha": alpha_loss.item(),
        "kl": kl_loss.item(),
    }
