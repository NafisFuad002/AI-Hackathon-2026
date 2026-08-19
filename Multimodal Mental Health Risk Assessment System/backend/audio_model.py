"""
audio_model.py
----------------
EATD-Corpus পেপার অনুযায়ী ট্রেনিং করা Voice/Audio depression detection
মডেলের architecture (NetVLAD + GRU) এবং mel spectrogram বের করার ফাংশন।

এই ফাইলটা ml_models.py থেকে import হয় - কোনো route/endpoint সরাসরি এটা
ব্যবহার করে না।

⚠️ এই ক্লাসগুলোর গঠন (layer সংখ্যা, dimension ইত্যাদি) Colab-এ যেভাবে
ট্রেনিং হয়েছিল তার সাথে হুবহু মিলতে হবে - নাহলে সেভ করা
voice_model.pth লোড করার সময় error আসবে (state_dict shape mismatch)।
"""

import numpy as np
import librosa
import torch
import torch.nn as nn
import torch.nn.functional as F

N_MELS = 40
SR = 16000


class NetVLAD(nn.Module):
    """Mel spectrogram এর ফ্রেমগুলোকে fixed-length embedding এ রূপান্তর করে।"""
    def __init__(self, feature_dim, num_clusters=8, out_dim=256):
        super().__init__()
        self.num_clusters = num_clusters
        self.feature_dim = feature_dim
        self.conv = nn.Conv1d(feature_dim, num_clusters, kernel_size=1, bias=True)
        self.centroids = nn.Parameter(torch.randn(num_clusters, feature_dim) * 0.01)
        self.proj = nn.Linear(num_clusters * feature_dim, out_dim)

    def forward(self, x):
        B, T, D = x.shape
        x_t = x.transpose(1, 2)
        soft_assign = self.conv(x_t)
        soft_assign = F.softmax(soft_assign, dim=1)

        x_expand = x.unsqueeze(1)
        centroids = self.centroids.unsqueeze(0).unsqueeze(2)
        residual = x_expand - centroids
        residual = residual * soft_assign.unsqueeze(-1)

        vlad = residual.sum(dim=2)
        vlad = F.normalize(vlad, p=2, dim=2)
        vlad = vlad.reshape(B, -1)
        vlad = F.normalize(vlad, p=2, dim=1)

        out = self.proj(vlad)
        return out


class AudioGRUNet(nn.Module):
    """Paper Table 2 অনুযায়ী GRU model architecture।"""
    def __init__(self, n_mels=N_MELS, netvlad_clusters=8, embed_dim=256,
                 gru_hidden=256, gru_layers=2, dropout=0.5):
        super().__init__()
        self.netvlad = NetVLAD(feature_dim=n_mels, num_clusters=netvlad_clusters, out_dim=embed_dim)
        self.gru = nn.GRU(input_size=embed_dim, hidden_size=gru_hidden,
                           num_layers=gru_layers, dropout=dropout, batch_first=True)
        self.drop1 = nn.Dropout(dropout)
        self.fc1 = nn.Linear(gru_hidden, gru_hidden)
        self.drop2 = nn.Dropout(dropout)
        self.fc2 = nn.Linear(gru_hidden, 2)

    def forward(self, mels_batch, device):
        all_embeds = []
        for sample_mels in mels_batch:
            resp_embeds = []
            for mel in sample_mels:
                x = torch.from_numpy(mel).unsqueeze(0).to(device)
                emb = self.netvlad(x)
                resp_embeds.append(emb)
            resp_embeds = torch.cat(resp_embeds, dim=0)
            all_embeds.append(resp_embeds)
        seq = torch.stack(all_embeds, dim=0)

        out, h_n = self.gru(seq)
        last = out[:, -1, :]
        x = self.drop1(last)
        x = F.relu(self.fc1(x))
        x = self.drop2(x)
        logits = self.fc2(x)
        return logits


def extract_mel(wav_path, n_mels=N_MELS, sr=SR):
    """একটা wav ফাইল থেকে normalized mel spectrogram বের করে (training এর মতোই)।"""
    y, orig_sr = librosa.load(wav_path, sr=sr)
    if len(y) < sr:
        y = np.pad(y, (0, sr - len(y)))
    mel = librosa.feature.melspectrogram(y=y, sr=sr, n_mels=n_mels, hop_length=512)
    mel_db = librosa.power_to_db(mel, ref=np.max)
    mel_db = (mel_db - mel_db.mean()) / (mel_db.std() + 1e-6)
    return mel_db.T.astype(np.float32)
