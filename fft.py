import numpy as np
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import librosa

def load_audio(filepath, sr=None):
    y, sr = librosa.load(filepath, sr=sr, mono=True)
    return sr, y

def generate_spectrogram(data, sample_rate, window_size=1024, hop_size=512):
    window = np.hanning(window_size)
    spectrogram = []

    for start in range(0, len(data) - window_size, hop_size):
        segment = data[start:start + window_size]
        windowed = segment * window
        spectrum = np.fft.fft(windowed)
        magnitude = np.abs(spectrum[:window_size // 2])
        spectrogram.append(magnitude)

    spectrogram = np.array(spectrogram).T  # transpose: rows=freqs, cols=time
    freqs = np.fft.fftfreq(window_size, d=1/sample_rate)[:window_size // 2]
    times = np.arange(0, len(data) - window_size, hop_size) / sample_rate
    return freqs, times, spectrogram

def plot_spectrogram(freqs, times, spectrogram):
    plt.figure(figsize=(10, 6))
    plt.imshow(20 * np.log10(spectrogram + 1e-8),  # dB scale
               aspect='auto', origin='lower',
               extent=[times[0], times[-1], freqs[0], freqs[-1]])
    plt.colorbar(label='Magnitude (dB)')
    plt.xlabel('Time (s)')
    plt.ylabel('Frequency (Hz)')
    plt.title('Spectrogram')
    plt.tight_layout()
    plt.show()


def animate_bars(freqs, spectrogram, fps=20, max_freq=10000):
    # Limit to frequencies <= max_freq
    max_bin = np.searchsorted(freqs, max_freq)
    freqs = freqs[:max_bin]
    spectrogram = spectrogram[:max_bin, :]

    fig, ax = plt.subplots()
    x = np.arange(len(freqs))

    ax.set_ylim(0, np.max(spectrogram))  # dB range
    ax.set_xlim(0, len(freqs))
    ax.set_xticks([])

    def update(frame):
        magnitudes = spectrogram[:, frame]
        bar_container = ax.bar(x, magnitudes, width=1.0)
        for bar, mag in zip(bar_container, magnitudes):
            bar.set_height(mag)
        return bar_container

    ani = animation.FuncAnimation(
        fig, update, frames=range(spectrogram.shape[1]),
        interval=1000 / fps, blit=True
    )

    plt.show()


# Example usage:
sample_rate, audio_data = load_audio("eldreth.mp3")
freqs, times, spec = generate_spectrogram(audio_data, sample_rate)

animate_bars(freqs, spec)



