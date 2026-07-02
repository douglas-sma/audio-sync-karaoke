#!/usr/bin/env python3
"""
Script para sincronizar audio vocal con instrumental para karaoke
Detecta automáticamente el offset usando correlación espectral (mel-spectrograma)
con verificación multi-ventana y fallback por onsets inteligentes.
"""

import numpy as np
import librosa
import soundfile as sf
from scipy import signal
import argparse
import os
import subprocess
from pathlib import Path
from mutagen import File as MutagenFile
from mutagen.mp4 import MP4


class AudioSynchronizer:
    def __init__(self, vocal_file, instrumental_file, output_dir="output"):
        self.vocal_file = vocal_file
        self.instrumental_file = instrumental_file
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)

        # Parámetros de calidad
        self.sample_rate = 44100
        self.duration_for_sync = 120
        self.max_allowed_offset = 5.0

        # Parámetros de correlación espectral
        self.n_mels = 128
        self.hop_length = 512
        self.n_fft = 2048
        self.min_spectral_corr = 0.30

        # Parámetros de multi-ventana
        self.sync_windows = [(0, 30), (30, 60), (60, 90)]
        self.max_window_std = 0.5

    # ──────────────────────────────────────────
    # CARGA DE AUDIO
    # ──────────────────────────────────────────

    def load_audio(self, file_path, duration=None):
        """Carga audio preservando canales originales."""
        print(f"Cargando {file_path}...")
        try:
            audio, sr = librosa.load(file_path, sr=self.sample_rate,
                                     duration=duration, mono=False)
            nch = 1 if audio.ndim == 1 else audio.shape[0]
            print(f"  -> Audio {'ESTÉREO' if nch > 1 else 'MONO'} detectado ({nch} canales)")
            return audio, sr
        except Exception as e:
            print(f"Error cargando {file_path}: {e}")
            return None, None

    # ──────────────────────────────────────────
    # FASE 1: PRE-PROCESAMIENTO ROBUSTO
    # ──────────────────────────────────────────

    def _preprocess_for_sync(self, audio):
        """
        Pre-procesa audio para correlación:
          - Filtro pasa-bandas 80-8000 Hz (elimina sub-bajos y agudos irrelevantes)
          - Normalización RMS
        """
        sos = signal.butter(4, [80, 8000], btype='band',
                            fs=self.sample_rate, output='sos')
        if audio.ndim == 1:
            filtered = signal.sosfilt(sos, audio)
        else:
            filtered = np.array([signal.sosfilt(sos, audio[ch])
                                 for ch in range(audio.shape[0])])
        rms = np.sqrt(np.mean(filtered ** 2))
        return filtered / (rms + 1e-8)

    def _rms_normalize(self, y):
        rms = np.sqrt(np.mean(y ** 2) + 1e-8)
        return y / rms

    def _to_mono(self, audio):
        return np.mean(audio, axis=0) if audio.ndim == 2 else audio

    def trim_leading_silence(self, audio, top_db=25):
        """Elimina silencio inicial con librosa.trim."""
        if audio.ndim == 1:
            y_trimmed, _ = librosa.effects.trim(audio, top_db=top_db)
            return y_trimmed
        else:
            start_times = []
            for ch in range(audio.shape[0]):
                _, index = librosa.effects.trim(audio[ch], top_db=top_db)
                start_times.append(index[0])
            min_start = min(start_times)
            return audio[:, min_start:]

    # ──────────────────────────────────────────
    # FASE 2: CORRELACIÓN ESPECTRAL
    # ──────────────────────────────────────────

    def _spectral_cross_correlation(self, vocal_mono, instrumental_mono):
        """
        Correlaciona dos señales mono usando mel-espectrogramas.
        Devuelve (offset_samples, offset_seconds, corr_strength).
        """
        # Mel-espectrogramas (escala de potencia → dB)
        S_v = librosa.feature.melspectrogram(
            y=vocal_mono, sr=self.sample_rate, n_mels=self.n_mels,
            n_fft=self.n_fft, hop_length=self.hop_length)
        S_i = librosa.feature.melspectrogram(
            y=instrumental_mono, sr=self.sample_rate, n_mels=self.n_mels,
            n_fft=self.n_fft, hop_length=self.hop_length)

        # Escala log-perceptual + normalización z-score por banda
        S_v_db = librosa.power_to_db(S_v, ref=np.max)
        S_i_db = librosa.power_to_db(S_i, ref=np.max)
        S_v_db = (S_v_db - np.mean(S_v_db)) / (np.std(S_v_db) + 1e-8)
        S_i_db = (S_i_db - np.mean(S_i_db)) / (np.std(S_i_db) + 1e-8)

        # Aplanar el tiempo: concatenar frames → vector 1D
        flat_v = S_v_db.ravel(order='F')
        flat_i = S_i_db.ravel(order='F')

        # Correlación 1D sobre los vectores aplanados
        corr = signal.correlate(flat_i, flat_v, mode='full')
        lags = signal.correlation_lags(len(flat_i), len(flat_v), mode='full')

        # Pico de correlación
        max_idx = np.argmax(np.abs(corr))
        corr_strength = np.max(np.abs(corr)) / (len(flat_v) + 1e-8)

        # Convertir lag de frames-espectro a segundos
        # Un frame = hop_length samples; la señal planar tiene n_frames = len(flat_v)/n_mels
        n_frames_v = S_v_db.shape[1]
        n_frames_i = S_i_db.shape[1]
        lag_frames = lags[max_idx]
        # Relación: lag_frames (en unidades de feature) → tiempo
        # Como aplanamos columnas, un lag = 1 columna = hop_length / sr segundos
        offset_seconds = lag_frames * self.hop_length / self.sample_rate
        # Escalar porque el lag está en "unidades de feature" (1 feature = 1 columna de espectrograma)
        # pero hemos concatenado n_mels filas → 1 lag unit = hop_length / sr seconds
        # y el lag está en el espacio de features aplanados (cada feature es una celda)
        # Esto no es correcto. Repensemos.

        # El vector aplanado tiene n_frames * n_mels elementos.
        # Un lag de 1 en el espacio aplanado corresponde a ~1/n_mels frames.
        # Mejor: correlacionar banda por banda y promediar.

        # ✅ Mejor enfoque: correlacionar cada banda mel por separado
        corr_bands = []
        for band in range(self.n_mels):
            c = signal.correlate(S_i_db[band], S_v_db[band], mode='same')
            corr_bands.append(c)
        mean_corr = np.mean(corr_bands, axis=0)

        # El array mean_corr tiene centro en len(mean_corr)//2 → lag=0
        # lags en este caso van de -n_frames/2 a +n_frames/2
        n_frames = S_v_db.shape[1]
        lag_samples = np.argmax(np.abs(mean_corr)) - n_frames  # relativo a 'same'
        # Convertir frames → segundos
        offset_seconds = lag_samples * self.hop_length / self.sample_rate
        corr_strength = np.max(np.abs(mean_corr)) / (self.n_mels + 1e-8)

        offset_samples = int(offset_seconds * self.sample_rate)
        return offset_samples, offset_seconds, corr_strength

    # ──────────────────────────────────────────
    # FASE 3: VERIFICACIÓN MULTI-VENTANA
    # ──────────────────────────────────────────

    def _find_offset_spectral(self, vocal, instrumental):
        """
        Calcula offset usando correlación espectral con verificación multi-ventana.
        Devuelve (offset_samples, offset_seconds) o None si falla.
        """
        print("Analizando sincronización con correlación espectral (mel-spectrograma)...")

        # Pre-procesar
        v_proc = self._preprocess_for_sync(vocal)
        i_proc = self._preprocess_for_sync(instrumental)

        v_mono = self._to_mono(v_proc)
        i_mono = self._to_mono(i_proc)

        offsets = []
        strengths = []

        for start, end in self.sync_windows:
            start_s = int(start * self.sample_rate)
            end_s = int(end * self.sample_rate)

            v_seg = v_mono[start_s:end_s]
            i_seg = i_mono[start_s:end_s]

            if len(v_seg) < self.sample_rate * 5 or len(i_seg) < self.sample_rate * 5:
                print(f"  Ventana {start}-{end}s: muy corta, saltando...")
                continue

            off_s, off_t, strength = self._spectral_cross_correlation(v_seg, i_seg)
            offsets.append(off_t)
            strengths.append(strength)
            print(f"  Ventana {start:3d}-{end:3d}s: offset={off_t:+.4f}s  confianza={strength:.3f}")

        if len(offsets) < 2:
            print("  No hay suficientes ventanas válidas para multi-ventana.")
            return None

        median_offset = np.median(offsets)
        std_offset = np.std(offsets)
        mean_strength = np.mean(strengths)

        print(f"  Resumen multi-ventana: mediana={median_offset:+.4f}s  std={std_offset:.4f}s  confianza media={mean_strength:.3f}")

        # Validaciones
        if std_offset > self.max_window_std:
            print(f"  ⚠️  Demasiada variación entre ventanas (std={std_offset:.3f}s > {self.max_window_std}s). Rechazando.")
            return None

        if mean_strength < self.min_spectral_corr:
            print(f"  ⚠️  Confianza espectral baja ({mean_strength:.3f} < {self.min_spectral_corr}). Rechazando.")
            return None

        if abs(median_offset) > self.max_allowed_offset:
            print(f"  ⚠️  Offset mediano ({median_offset:.3f}s) excede límite ({self.max_allowed_offset}s). Rechazando.")
            return None

        # Validación cruzada con onsets para offsets grandes (> 2s)
        if abs(median_offset) > 2.0:
            print(f"  → Offset > 2s, verificando con onsets...")
            _, onset_offset = self.find_onset_based_sync(vocal, instrumental)
            if abs(onset_offset) > 0.1 and abs(onset_offset - median_offset) > 1.0:
                print(f"  ⚠️  Los onsets indican {onset_offset:+.3f}s (diferencia > 1s). Rechazando offset espectral.")
                return None
            print(f"  → Onsets confirman ({onset_offset:+.3f}s).")

        offset_samples = int(median_offset * self.sample_rate)
        print(f"  ✅ Offset espectral final: {median_offset:.4f}s (confianza: {mean_strength:.3f})")
        return offset_samples, median_offset

    # ──────────────────────────────────────────
    # FASE 4: ONSET MATCHING INTELIGENTE
    # ──────────────────────────────────────────

    def _get_onsets(self, audio):
        """Detecta onsets en el audio (mono o estéreo)."""
        y_mono = self._to_mono(audio)
        onset_env = librosa.onset.onset_strength(y=y_mono, sr=self.sample_rate)
        onsets = librosa.onset.onset_detect(
            onset_envelope=onset_env, sr=self.sample_rate, units='time',
            delta=0.12, wait=0.1)
        return onsets

    def find_onset_based_sync(self, vocal, instrumental):
        """
        Encuentra offset por correspondencia de onsets con proximity matching.
        No asume correspondencia 1:1 — busca el onset instrumental más cercano
        para cada onset vocal y filtra outliers con IQR.
        """
        print("Analizando sincronización basada en onsets (proximity matching)...")

        vocal_onsets = self._get_onsets(vocal)
        inst_onsets = self._get_onsets(instrumental)

        print(f"  Onsets vocales: {len(vocal_onsets)}  instrumentales: {len(inst_onsets)}")

        if len(vocal_onsets) < 3 or len(inst_onsets) < 3:
            print("  No hay suficientes onsets (< 3).")
            return 0, 0.0

        # Proximity matching: para cada onset vocal, buscar el onset instrumental más cercano
        diffs = []
        for v_onset in vocal_onsets[:30]:  # usar primeros 30 onsets
            closest = min(inst_onsets, key=lambda x: abs(x - v_onset))
            diff = closest - v_onset
            diffs.append(diff)

        # Filtrar outliers con IQR
        diffs = np.array(diffs)
        q1, q3 = np.percentile(diffs, [25, 75])
        iqr = q3 - q1
        filtered = diffs[(diffs >= q1 - 1.5 * iqr) & (diffs <= q3 + 1.5 * iqr)]
        n_outliers = len(diffs) - len(filtered)

        if len(filtered) < 3:
            print("  No hay suficientes pares válidos tras filtrar outliers.")
            return 0, 0.0

        offset_seconds = float(np.median(filtered))
        offset_samples = int(offset_seconds * self.sample_rate)

        print(f"  Offset por onsets: {offset_seconds:+.4f}s (pares: {len(filtered)}/{len(diffs)}, outliers eliminados: {n_outliers})")
        return offset_samples, offset_seconds

    # ──────────────────────────────────────────
    # FASE 5: PIPELINE INTEGRADO
    # ──────────────────────────────────────────

    def _find_offset(self, vocal, instrumental, method='auto'):
        """
        Pipeline de detección de offset en cascada:

          1. auto (default): espectral multi-ventana → onsets → legado
          2. cross_correlation: correlación de ondas legacy (con mejoras)
          3. onset: onsets inteligentes

        Devuelve (offset_samples, offset_seconds).
        """
        if method == 'onset':
            return self.find_onset_based_sync(vocal, instrumental)

        if method == 'cross_correlation':
            # Método legacy mejorado con pre-procesamiento y capping
            return self._find_offset_legacy(vocal, instrumental)

        # ── AUTO: cascada espectral → onsets → legado ──
        result = self._find_offset_spectral(vocal, instrumental)
        if result is not None:
            return result

        print("\n→ Fallback 1: onsets inteligentes")
        off_s, off_t = self.find_onset_based_sync(vocal, instrumental)
        if abs(off_t) > 0.1 and abs(off_t) <= self.max_allowed_offset:
            return off_s, off_t

        print("\n→ Fallback 2: correlación de ondas legacy")
        return self._find_offset_legacy(vocal, instrumental)

    def _find_offset_legacy(self, vocal, instrumental):
        """
        Método legacy de correlación de ondas con mejoras:
          - Pre-procesamiento (bandpass + RMS normalize)
          - Búsqueda limitada al rango [-max_allowed_offset, +max_allowed_offset]
          - Capping forzoso
        """
        print("(correlación de ondas legacy)...")

        v_proc = self._preprocess_for_sync(vocal)
        i_proc = self._preprocess_for_sync(instrumental)
        v_mono = self._to_mono(v_proc)
        i_mono = self._to_mono(i_proc)

        max_s = min(len(v_mono), len(i_mono), self.sample_rate * self.duration_for_sync)
        v_seg = self._rms_normalize(v_mono[:max_s])
        i_seg = self._rms_normalize(i_mono[:max_s])

        corr = signal.correlate(i_seg, v_seg, mode='full')
        lags = signal.correlation_lags(len(i_seg), len(v_seg), mode='full')

        # Restringir búsqueda al rango permitido
        max_lag = int(self.max_allowed_offset * self.sample_rate)
        valid = np.abs(lags) <= max_lag
        if np.any(valid):
            corr_restricted = np.abs(corr) * valid
        else:
            corr_restricted = np.abs(corr)

        max_idx = np.argmax(corr_restricted)
        offset_samples = lags[max_idx]
        offset_seconds = offset_samples / self.sample_rate
        corr_value = np.abs(corr[max_idx]) / (len(v_seg) + 1e-8)

        print(f"  Offset legacy: {offset_seconds:+.4f}s  correlación={corr_value:.3f}")

        # Capping si excede el límite (por si la restricción falló)
        if abs(offset_seconds) > self.max_allowed_offset:
            offset_samples = int(np.sign(offset_samples) * self.max_allowed_offset * self.sample_rate)
            offset_seconds = offset_samples / self.sample_rate
            print(f"  → Capping forzoso a {offset_seconds:.3f}s")

        return offset_samples, offset_seconds

    # ──────────────────────────────────────────
    # FASE 6: APLICAR SINCRONIZACIÓN
    # ──────────────────────────────────────────

    def apply_sync_adjustment(self, vocal, offset_samples):
        """Aplica el ajuste de sincronización (padding/truncado) con validación."""
        sr = self.sample_rate
        max_allowed = int(self.max_allowed_offset * sr)

        # Capping de seguridad
        if abs(offset_samples) > max_allowed:
            print(f"⚠️  Offset ({offset_samples/sr:.2f}s) excede máximo ({self.max_allowed_offset}s). Limitando.")
            offset_samples = int(np.sign(offset_samples) * max_allowed)

        print(f"Aplicando ajuste de sincronización...")

        if offset_samples > 0:
            # Retrasar vocal: añadir silencio al inicio
            if vocal.ndim == 1:
                sync_vocal = np.concatenate([np.zeros(offset_samples), vocal])
            else:
                sync_vocal = np.concatenate([np.zeros((vocal.shape[0], offset_samples)), vocal], axis=1)
            print(f"  → Agregando {offset_samples/sr:.3f}s de silencio al inicio")

        elif offset_samples < 0:
            # Adelantar vocal: cortar del inicio
            cut = abs(offset_samples)
            vlen = vocal.shape[1] if vocal.ndim == 2 else len(vocal)
            if cut >= vlen:
                print("  ⚠️ Corte mayor que duración. Sin ajuste.")
                return vocal
            if vocal.ndim == 1:
                sync_vocal = vocal[cut:]
            else:
                sync_vocal = vocal[:, cut:]
            print(f"  → Cortando {cut/sr:.3f}s del inicio")

        else:
            sync_vocal = vocal
            print("  ✓ No se requiere ajuste de timing")

        return sync_vocal

    # ──────────────────────────────────────────
    # MEJORA DE CALIDAD
    # ──────────────────────────────────────────

    def enhance_audio_quality(self, audio):
        """Filtro pasa-altos suave (30 Hz) + normalización conservadora."""
        print("Aplicando mejoras de calidad...")
        sos = signal.butter(2, 30, btype='high', fs=self.sample_rate, output='sos')

        if audio.ndim == 1:
            filtered = signal.sosfilt(sos, audio)
        else:
            filtered = np.zeros_like(audio)
            for ch in range(audio.shape[0]):
                filtered[ch] = signal.sosfilt(sos, audio[ch])

        max_val = np.max(np.abs(filtered))
        if max_val > 0:
            filtered = filtered * (0.944 / max_val)
        return filtered

    # ──────────────────────────────────────────
    # GUARDADO Y METADATOS
    # ──────────────────────────────────────────

    def save_high_quality_audio(self, audio, filename):
        temp_wav = self.output_dir / "temp_output.wav"
        out_path = self.output_dir / Path(filename).with_suffix('.m4a')

        audio_to_save = audio.T if audio.ndim == 2 else audio
        print(f"Procesando audio {'ESTÉREO' if audio.ndim == 2 else 'MONO'}...")

        sf.write(temp_wav, audio_to_save, self.sample_rate, subtype='PCM_24')
        self.convert_to_m4a(temp_wav, out_path)

        if temp_wav.exists():
            os.remove(temp_wav)
        return out_path

    def convert_to_m4a(self, wav_path, m4a_path):
        try:
            cmd = [
                'ffmpeg', '-i', str(wav_path),
                '-codec:a', 'aac',
                '-b:a', '256k',
                '-q:a', '2',
                '-y',
                str(m4a_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"M4A creado: {m4a_path}")
            else:
                print(f"Error creando M4A: {result.stderr}")
        except FileNotFoundError:
            print("FFmpeg no encontrado. Instala con: sudo apt install ffmpeg")

    def copy_metadata_with_sync_title(self, source_file, dest_file):
        try:
            source_audio = MutagenFile(source_file)
            if source_audio is None:
                print(f"No se pudieron leer metadatos de: {source_file}")
                return

            dest_audio = MP4(dest_file)
            original_title = None

            if hasattr(source_audio, 'tags') and source_audio.tags:
                tags = source_audio.tags

                # ID3 (MP3)
                if hasattr(tags, 'getall'):
                    title_tags = tags.getall('TIT2')
                    if title_tags:
                        original_title = str(title_tags[0])
                    id3_to_mp4 = {
                        'TIT2': '\xa9nam', 'TPE1': '\xa9ART', 'TALB': '\xa9alb',
                        'TPE2': 'aART', 'TDRC': '\xa9day', 'TCON': '\xa9gen',
                        'TCOM': '\xa9wrt',
                    }
                    for id3_tag, mp4_tag in id3_to_mp4.items():
                        try:
                            values = tags.getall(id3_tag)
                            if values:
                                dest_audio[mp4_tag] = [str(values[0])]
                        except Exception:
                            pass

                # Vorbis (FLAC, OGG)
                elif isinstance(tags, dict) or hasattr(tags, 'items'):
                    for key, value in tags.items():
                        kl = key.lower() if isinstance(key, str) else str(key).lower()
                        if 'title' in kl:
                            original_title = value[0] if isinstance(value, list) else str(value)
                        vorbis_map = {
                            'title': '\xa9nam', 'artist': '\xa9ART', 'album': '\xa9alb',
                            'albumartist': 'aART', 'date': '\xa9day', 'genre': '\xa9gen',
                            'composer': '\xa9wrt',
                        }
                        for vk, mp4_tag in vorbis_map.items():
                            if vk in kl:
                                try:
                                    dest_audio[mp4_tag] = [str(value[0] if isinstance(value, list) else value)]
                                except Exception:
                                    pass

                # MP4 existente
                elif hasattr(source_audio, 'get'):
                    if '\xa9nam' in source_audio:
                        original_title = source_audio['\xa9nam'][0]
                    for tag in ('\xa9nam', '\xa9ART', '\xa9alb', 'aART', '\xa9day',
                                '\xa9gen', '\xa9wrt', '\xa9cmt', 'trkn', 'disk', 'covr'):
                        if tag in source_audio:
                            try:
                                dest_audio[tag] = source_audio[tag]
                            except Exception:
                                pass

            # Título con "(Sincronizado)"
            if original_title:
                new_title = f"{original_title} (Sincronizado)"
            else:
                new_title = f"{Path(self.vocal_file).stem} (Sincronizado)"
            dest_audio['\xa9nam'] = [new_title]
            dest_audio.save()
            print(f"Metadatos copiados. Nuevo título: {new_title}")

        except Exception as e:
            print(f"Error copiando metadatos: {e}")

    def create_karaoke_mix(self, synchronized_vocal, instrumental):
        print("Creando mezcla de karaoke...")
        min_len = min(len(synchronized_vocal), len(instrumental))
        mix = instrumental[:min_len] + (synchronized_vocal[:min_len] * 0.3)
        max_val = np.max(np.abs(mix))
        if max_val > 0:
            mix = mix * (0.891 / max_val)
        return mix

    # ──────────────────────────────────────────
    # FASE 7: SINCRONIZACIÓN PRINCIPAL
    # ──────────────────────────────────────────

    def synchronize(self, method='auto'):
        """
        Proceso principal de sincronización.

        Args:
            method: 'auto' (cascada spectral→onsets→legacy),
                    'cross_correlation' (legacy),
                    'onset' (onsets inteligentes)
        """
        print("=== SINCRONIZADOR DE AUDIO PARA KARAOKE (v3.0) ===")
        print(f"Vocal: {self.vocal_file}")
        print(f"Instrumental: {self.instrumental_file}")
        print(f"Método: {method}")
        print()

        # Cargar
        vocal, vocal_sr = self.load_audio(self.vocal_file)
        instrumental, inst_sr = self.load_audio(self.instrumental_file)

        if vocal is None or instrumental is None:
            print("Error: No se pudieron cargar los archivos de audio")
            return False

        v_dur = (vocal.shape[1] if vocal.ndim == 2 else len(vocal)) / vocal_sr
        i_dur = (instrumental.shape[1] if instrumental.ndim == 2 else len(instrumental)) / inst_sr
        print(f"Duración vocal: {v_dur:.2f}s  instrumental: {i_dur:.2f}s")
        print()

        # Pipeline de detección de offset
        offset_samples, offset_seconds = self._find_offset(vocal, instrumental, method=method)
        print()

        # Aplicar sincronización
        synchronized_vocal = self.apply_sync_adjustment(vocal, offset_samples)

        # Normalización conservadora (sin filtro para preservar frecuencias originales)
        print("Aplicando normalización conservadora...")
        max_val = np.max(np.abs(synchronized_vocal))
        if max_val > 0:
            enhanced_vocal = synchronized_vocal * (0.98 / max_val)
        else:
            enhanced_vocal = synchronized_vocal

        # Guardar
        print("\nGuardando archivo vocal sincronizado...")
        output_path = self.save_high_quality_audio(enhanced_vocal, "vocal_sincronizado.wav")

        # Metadatos
        print("\nCopiando metadatos del archivo original...")
        self.copy_metadata_with_sync_title(self.vocal_file, output_path)

        print(f"\n✅ Sincronización completada!")
        print(f"   Archivo: {self.output_dir / 'vocal_sincronizado.m4a'}")
        print(f"   Offset aplicado: {offset_seconds:.3f}s")
        return True


def main():
    parser = argparse.ArgumentParser(description='Sincronizar audio vocal con instrumental para karaoke')
    parser.add_argument('--vocal', required=True, help='Archivo de audio vocal')
    parser.add_argument('--instrumental', required=True, help='Archivo instrumental')
    parser.add_argument('--output', default='output', help='Directorio de salida')
    parser.add_argument('--method', choices=['auto', 'cross_correlation', 'onset'],
                        default='auto',
                        help='Método: auto (recomendado, cascada espectral→onsets→legacy), '
                             'cross_correlation (legacy), onset (onsets inteligentes)')

    args = parser.parse_args()

    if not os.path.exists(args.vocal):
        print(f"Error: Archivo vocal no encontrado: {args.vocal}")
        return
    if not os.path.exists(args.instrumental):
        print(f"Error: Archivo instrumental no encontrado: {args.instrumental}")
        return

    sync = AudioSynchronizer(args.vocal, args.instrumental, args.output)
    success = sync.synchronize(method=args.method)

    if success:
        print("\n🎵 ¡Listo para karaoke! 🎤")
    else:
        print("\n❌ Error en la sincronización")


if __name__ == "__main__":
    main()
