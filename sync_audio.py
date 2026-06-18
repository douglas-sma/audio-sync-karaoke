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
from mutagen import File as MutagenFile
from mutagen.mp4 import MP4

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
        Guarda audio en alta calidad en formato M4A (preservando mono/estéreo)
        """
        # Crear archivo WAV temporal
        temp_wav_path = self.output_dir / "temp_output.wav"
        output_path = self.output_dir / Path(filename).with_suffix('.m4a')
        
        # Preparar audio para guardado
        if audio.ndim == 2:
            # Audio estéreo - transponer para soundfile (samples, channels)
            audio_to_save = audio.T
            print(f"Procesando audio ESTÉREO...")
        else:
            # Audio mono
            audio_to_save = audio
            print(f"Procesando audio MONO...")
        
        # Guardar WAV temporal
        sf.write(temp_wav_path, audio_to_save, self.sample_rate, subtype='PCM_24')
        
        # Convertir a M4A de alta calidad
        self.convert_to_m4a(temp_wav_path, output_path)
        
        # Eliminar archivo WAV temporal
        if temp_wav_path.exists():
            os.remove(temp_wav_path)
        
        return output_path
    
    def convert_to_m4a(self, wav_path, m4a_path):
        """
        Convierte WAV a M4A (AAC) de alta calidad usando FFmpeg
        """
        try:
            cmd = [
                'ffmpeg', '-i', str(wav_path),
                '-codec:a', 'aac',
                '-b:a', '256k',  # Bitrate alto para AAC
                '-q:a', '2',     # Calidad alta
                '-y',            # Sobrescribir
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
        """
        Copia los metadatos del archivo original al archivo sincronizado
        y agrega 'Sincronizado' al título
        """
        try:
            # Leer metadatos del archivo original
            source_audio = MutagenFile(source_file)
            if source_audio is None:
                print(f"No se pudieron leer metadatos de: {source_file}")
                return
            
            # Abrir archivo de destino (M4A/MP4)
            dest_audio = MP4(dest_file)
            
            # Mapeo de tags comunes entre formatos
            # Tags MP4 usan el formato iTunes
            mp4_tags_map = {
                'title': '\xa9nam',
                'artist': '\xa9ART',
                'album': '\xa9alb',
                'albumartist': 'aART',
                'date': '\xa9day',
                'genre': '\xa9gen',
                'composer': '\xa9wrt',
                'comment': '\xa9cmt',
                'tracknumber': 'trkn',
                'discnumber': 'disk',
            }
            
            original_title = None
            
            # Copiar metadatos según el tipo de archivo fuente
            if hasattr(source_audio, 'tags') and source_audio.tags:
                tags = source_audio.tags
                
                # Intentar obtener título del archivo original
                # Para archivos MP3 (ID3)
                if hasattr(tags, 'getall'):
                    title_tags = tags.getall('TIT2')
                    if title_tags:
                        original_title = str(title_tags[0])
                    
                    # Copiar tags ID3 a MP4
                    id3_to_mp4 = {
                        'TIT2': '\xa9nam',  # Título
                        'TPE1': '\xa9ART',  # Artista
                        'TALB': '\xa9alb',  # Álbum
                        'TPE2': 'aART',     # Artista del álbum
                        'TDRC': '\xa9day',  # Fecha
                        'TCON': '\xa9gen',  # Género
                        'TCOM': '\xa9wrt',  # Compositor
                    }
                    
                    for id3_tag, mp4_tag in id3_to_mp4.items():
                        try:
                            values = tags.getall(id3_tag)
                            if values:
                                dest_audio[mp4_tag] = [str(values[0])]
                        except:
                            pass
                
                # Para archivos FLAC, OGG, etc. (Vorbis Comments)
                elif isinstance(tags, dict) or hasattr(tags, 'items'):
                    for key, value in tags.items():
                        key_lower = key.lower() if isinstance(key, str) else str(key).lower()
                        
                        if 'title' in key_lower:
                            if isinstance(value, list):
                                original_title = value[0]
                            else:
                                original_title = str(value)
                        
                        # Mapear tags de Vorbis a MP4
                        vorbis_to_mp4 = {
                            'title': '\xa9nam',
                            'artist': '\xa9ART',
                            'album': '\xa9alb',
                            'albumartist': 'aART',
                            'date': '\xa9day',
                            'genre': '\xa9gen',
                            'composer': '\xa9wrt',
                        }
                        
                        for vorbis_key, mp4_tag in vorbis_to_mp4.items():
                            if vorbis_key in key_lower:
                                try:
                                    if isinstance(value, list):
                                        dest_audio[mp4_tag] = [str(value[0])]
                                    else:
                                        dest_audio[mp4_tag] = [str(value)]
                                except:
                                    pass
                
                # Para archivos M4A/MP4 ya existentes
                elif hasattr(source_audio, 'get'):
                    if '\xa9nam' in source_audio:
                        original_title = source_audio['\xa9nam'][0]
                    
                    # Copiar todos los tags directamente
                    for tag in mp4_tags_map.values():
                        if tag in source_audio:
                            try:
                                dest_audio[tag] = source_audio[tag]
                            except:
                                pass
                    
                    # Copiar carátula si existe
                    if 'covr' in source_audio:
                        dest_audio['covr'] = source_audio['covr']
            
            # Modificar el título agregando "Sincronizado"
            if original_title:
                new_title = f"{original_title} (Sincronizado)"
            else:
                # Si no hay título, usar el nombre del archivo
                original_name = Path(self.vocal_file).stem
                new_title = f"{original_name} (Sincronizado)"
            
            dest_audio['\xa9nam'] = [new_title]
            
            # Guardar cambios
            dest_audio.save()
            print(f"Metadatos copiados. Nuevo título: {new_title}")
            
        except Exception as e:
            print(f"Error copiando metadatos: {e}")
    
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
        output_path = self.save_high_quality_audio(enhanced_vocal, "vocal_sincronizado.wav")
        
        # Copiar metadatos del archivo original y modificar título
        print("\nCopiando metadatos del archivo original...")
        self.copy_metadata_with_sync_title(self.vocal_file, output_path)
        
        print(f"\n✅ Sincronización completada!")
        print(f"📁 Archivo guardado en: {self.output_dir}")
        print(f"⏱️  Offset aplicado: {offset_seconds:.3f} segundos")
        print(f"🎵 Archivo listo: vocal_sincronizado.m4a")
        
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
