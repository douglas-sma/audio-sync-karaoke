#!/usr/bin/env python3
"""
Script para sincronizar audio vocal con instrumental para karaoke
Detecta automáticamente el offset y ajusta la sincronización
"""

import numpy as np
import librosa
import soundfile as sf
from scipy import signal
import argparse
import os
import subprocess
from pathlib import Path

class AudioSynchronizer:
    def __init__(self, vocal_file, instrumental_file, output_dir="output"):
        self.vocal_file = vocal_file
        self.instrumental_file = instrumental_file
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        # Parámetros de calidad
        self.sample_rate = 44100  # CD quality
        self.duration_for_sync = 60  # Primeros 60 segundos para análisis
        
    def load_audio(self, file_path, duration=None):
        """Carga audio con librosa manteniendo alta calidad y canales originales"""
        print(f"Cargando {file_path}...")
        try:
            # Cargar preservando estéreo (mono=False mantiene los canales originales)
            audio, sr = librosa.load(file_path, sr=self.sample_rate, duration=duration, mono=False)
            
            # Verificar si es mono o estéreo
            if audio.ndim == 1:
                print(f"  -> Audio MONO detectado")
                channels = "mono"
            else:
                print(f"  -> Audio ESTÉREO detectado ({audio.shape[0]} canales)")
                channels = "stereo"
            
            return audio, sr
        except Exception as e:
            print(f"Error cargando {file_path}: {e}")
            return None, None
    
    def find_offset_cross_correlation(self, vocal, instrumental):
        """
        Encuentra el offset usando correlación cruzada
        Método más preciso para sincronización (funciona con mono y estéreo)
        """
        print("Analizando sincronización con correlación cruzada...")
        
        # Convertir a mono para análisis si es necesario (preservando el audio original)
        def to_mono_for_analysis(audio):
            if audio.ndim == 2:
                # Si es estéreo, usar el promedio de los canales para análisis
                return np.mean(audio, axis=0)
            return audio
        
        vocal_mono = to_mono_for_analysis(vocal)
        instrumental_mono = to_mono_for_analysis(instrumental)
        
        # Usar solo una porción para el análisis (más rápido)
        max_samples = min(len(vocal_mono), len(instrumental_mono), self.sample_rate * self.duration_for_sync)
        vocal_segment = vocal_mono[:max_samples]
        instrumental_segment = instrumental_mono[:max_samples]
        
        # Normalizar audio
        vocal_segment = vocal_segment / (np.max(np.abs(vocal_segment)) + 1e-8)
        instrumental_segment = instrumental_segment / (np.max(np.abs(instrumental_segment)) + 1e-8)
        
        # Correlación cruzada
        correlation = signal.correlate(instrumental_segment, vocal_segment, mode='full')
        
        # Encontrar el pico de correlación
        lags = signal.correlation_lags(len(instrumental_segment), len(vocal_segment), mode='full')
        max_corr_idx = np.argmax(np.abs(correlation))
        offset_samples = lags[max_corr_idx]
        offset_seconds = offset_samples / self.sample_rate
        
        print(f"Offset detectado: {offset_seconds:.3f} segundos ({offset_samples} samples)")
        print(f"Correlación máxima: {np.max(np.abs(correlation)):.3f}")
        
        return offset_samples, offset_seconds
    
    def find_onset_based_sync(self, vocal, instrumental):
        """
        Método alternativo basado en detección de onset
        """
        print("Analizando sincronización basada en onsets...")
        
        # Detectar onsets en ambos audios
        vocal_onsets = librosa.onset.onset_detect(y=vocal, sr=self.sample_rate, units='time')
        instrumental_onsets = librosa.onset.onset_detect(y=instrumental, sr=self.sample_rate, units='time')
        
        if len(vocal_onsets) > 0 and len(instrumental_onsets) > 0:
            # Calcular diferencia entre primeros onsets
            offset_seconds = instrumental_onsets[0] - vocal_onsets[0]
            offset_samples = int(offset_seconds * self.sample_rate)
            
            print(f"Primer onset vocal: {vocal_onsets[0]:.3f}s")
            print(f"Primer onset instrumental: {instrumental_onsets[0]:.3f}s")
            print(f"Offset calculado: {offset_seconds:.3f}s")
            
            return offset_samples, offset_seconds
        
        return 0, 0.0
    
    def apply_sync_adjustment(self, vocal, offset_samples):
        """
        Aplica el ajuste de sincronización al audio vocal (mono o estéreo)
        """
        print(f"Aplicando ajuste de sincronización...")
        
        if offset_samples > 0:
            # El vocal necesita retrasarse (agregar silencio al inicio)
            if vocal.ndim == 1:
                # Audio mono
                silence = np.zeros(offset_samples)
                synchronized_vocal = np.concatenate([silence, vocal])
            else:
                # Audio estéreo
                silence = np.zeros((vocal.shape[0], offset_samples))
                synchronized_vocal = np.concatenate([silence, vocal], axis=1)
            print(f"Agregando {offset_samples/self.sample_rate:.3f}s de silencio al inicio")
            
        elif offset_samples < 0:
            # El vocal necesita adelantarse (cortar del inicio)
            cut_samples = abs(offset_samples)
            vocal_length = vocal.shape[1] if vocal.ndim == 2 else len(vocal)
            
            if cut_samples < vocal_length:
                if vocal.ndim == 1:
                    # Audio mono
                    synchronized_vocal = vocal[cut_samples:]
                else:
                    # Audio estéreo
                    synchronized_vocal = vocal[:, cut_samples:]
                print(f"Cortando {cut_samples/self.sample_rate:.3f}s del inicio")
            else:
                print("¡Error! El corte es mayor que la duración del audio")
                return vocal
        else:
            # No necesita ajuste
            synchronized_vocal = vocal
            print("No se requiere ajuste de timing")
        
        return synchronized_vocal
    
    def enhance_audio_quality(self, audio):
        """
        Mejora la calidad del audio aplicando filtros suaves (mono o estéreo)
        """
        print("Aplicando mejoras de calidad...")
        
        # Filtro pasa-altos más suave para remover solo ruido muy bajo
        sos = signal.butter(2, 30, btype='high', fs=self.sample_rate, output='sos')  # Filtro más suave
        
        if audio.ndim == 1:
            # Audio mono
            filtered_audio = signal.sosfilt(sos, audio)
            # Normalización más agresiva para mantener volumen
            max_val = np.max(np.abs(filtered_audio))
            if max_val > 0:
                # Normalizar a -0.5dB en lugar de -1dB para más volumen
                filtered_audio = filtered_audio * (0.944 / max_val)
        else:
            # Audio estéreo - procesar cada canal
            filtered_audio = np.zeros_like(audio)
            for channel in range(audio.shape[0]):
                filtered_audio[channel] = signal.sosfilt(sos, audio[channel])
            
            # Normalización más agresiva del audio estéreo
            max_val = np.max(np.abs(filtered_audio))
            if max_val > 0:
                filtered_audio = filtered_audio * (0.944 / max_val)
        
        return filtered_audio
    
    def save_high_quality_audio(self, audio, filename):
        """
        Guarda audio en alta calidad (preservando mono/estéreo)
        """
        output_path = self.output_dir / filename
        
        # Preparar audio para guardado
        if audio.ndim == 2:
            # Audio estéreo - transponer para soundfile (samples, channels)
            audio_to_save = audio.T
            print(f"Guardando audio ESTÉREO: {output_path}")
        else:
            # Audio mono
            audio_to_save = audio
            print(f"Guardando audio MONO: {output_path}")
        
        # Guardar como WAV sin compresión para máxima calidad
        sf.write(output_path, audio_to_save, self.sample_rate, subtype='PCM_24')
        
        # También crear versión MP3 de alta calidad
        mp3_path = output_path.with_suffix('.mp3')
        self.convert_to_mp3(output_path, mp3_path)
        
        return output_path
    
    def convert_to_mp3(self, wav_path, mp3_path):
        """
        Convierte WAV a MP3 de alta calidad usando FFmpeg
        """
        try:
            cmd = [
                'ffmpeg', '-i', str(wav_path),
                '-codec:a', 'libmp3lame',
                '-b:a', '320k',  # Bitrate máximo
                '-q:a', '0',     # Calidad máxima
                '-y',            # Sobrescribir
                str(mp3_path)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print(f"MP3 creado: {mp3_path}")
            else:
                print(f"Error creando MP3: {result.stderr}")
                
        except FileNotFoundError:
            print("FFmpeg no encontrado. Instala con: sudo apt install ffmpeg")
    
    def create_karaoke_mix(self, synchronized_vocal, instrumental):
        """
        Crea una mezcla de karaoke combinando vocal e instrumental
        """
        print("Creando mezcla de karaoke...")
        
        # Asegurar que ambos audios tengan la misma longitud
        min_length = min(len(synchronized_vocal), len(instrumental))
        vocal_trimmed = synchronized_vocal[:min_length]
        instrumental_trimmed = instrumental[:min_length]
        
        # Mezclar con balance adecuado
        # Instrumental al 100%, vocal al 30% para karaoke
        karaoke_mix = instrumental_trimmed + (vocal_trimmed * 0.3)
        
        # Normalizar la mezcla
        max_val = np.max(np.abs(karaoke_mix))
        if max_val > 0:
            karaoke_mix = karaoke_mix * (0.891 / max_val)
        
        return karaoke_mix
    
    def synchronize(self, method='cross_correlation'):
        """
        Proceso principal de sincronización
        """
        print("=== SINCRONIZADOR DE AUDIO PARA KARAOKE ===")
        print(f"Vocal: {self.vocal_file}")
        print(f"Instrumental: {self.instrumental_file}")
        print()
        
        # Cargar archivos de audio
        vocal, vocal_sr = self.load_audio(self.vocal_file)
        instrumental, instrumental_sr = self.load_audio(self.instrumental_file)
        
        if vocal is None or instrumental is None:
            print("Error: No se pudieron cargar los archivos de audio")
            return False
        
        print(f"Duración vocal: {(vocal.shape[1] if vocal.ndim == 2 else len(vocal))/vocal_sr:.2f} segundos")
        print(f"Duración instrumental: {(instrumental.shape[1] if instrumental.ndim == 2 else len(instrumental))/instrumental_sr:.2f} segundos")
        print()
        
        # Encontrar offset de sincronización
        if method == 'cross_correlation':
            offset_samples, offset_seconds = self.find_offset_cross_correlation(vocal, instrumental)
        elif method == 'onset':
            offset_samples, offset_seconds = self.find_onset_based_sync(vocal, instrumental)
        else:
            print("Método no válido")
            return False
        
        # Aplicar sincronización
        synchronized_vocal = self.apply_sync_adjustment(vocal, offset_samples)
        
        # Mantener frecuencias originales (solo normalización conservadora)
        print("Preservando frecuencias originales...")
        if synchronized_vocal.ndim == 1:
            max_val = np.max(np.abs(synchronized_vocal))
            if max_val > 0:
                enhanced_vocal = synchronized_vocal * (0.98 / max_val)  # Normalización muy conservadora
            else:
                enhanced_vocal = synchronized_vocal
        else:
            max_val = np.max(np.abs(synchronized_vocal))
            if max_val > 0:
                enhanced_vocal = synchronized_vocal * (0.98 / max_val)
            else:
                enhanced_vocal = synchronized_vocal
        
        # Guardar solo el vocal sincronizado
        print("\nGuardando archivo vocal sincronizado...")
        self.save_high_quality_audio(enhanced_vocal, "vocal_sincronizado.wav")
        
        print(f"\n✅ Sincronización completada!")
        print(f"📁 Archivo guardado en: {self.output_dir}")
        print(f"⏱️  Offset aplicado: {offset_seconds:.3f} segundos")
        print(f"🎵 Archivo listo: vocal_sincronizado.mp3")
        
        return True

def main():
    parser = argparse.ArgumentParser(description='Sincronizar audio vocal con instrumental')
    parser.add_argument('--vocal', required=True, help='Archivo de audio vocal')
    parser.add_argument('--instrumental', required=True, help='Archivo instrumental')
    parser.add_argument('--output', default='output', help='Directorio de salida')
    parser.add_argument('--method', choices=['cross_correlation', 'onset'], 
                       default='cross_correlation', help='Método de sincronización')
    
    args = parser.parse_args()
    
    # Verificar que los archivos existen
    if not os.path.exists(args.vocal):
        print(f"Error: Archivo vocal no encontrado: {args.vocal}")
        return
    
    if not os.path.exists(args.instrumental):
        print(f"Error: Archivo instrumental no encontrado: {args.instrumental}")
        return
    
    # Crear sincronizador y procesar
    sync = AudioSynchronizer(args.vocal, args.instrumental, args.output)
    success = sync.synchronize(method=args.method)
    
    if success:
        print("\n🎵 ¡Listo para karaoke! 🎤")
    else:
        print("\n❌ Error en la sincronización")

if __name__ == "__main__":
    main()
