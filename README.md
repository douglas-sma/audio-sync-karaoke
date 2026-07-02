# 🎵 Sync Songs — Sincronizador de Audio para Karaoke

Sincroniza automáticamente un audio vocal con su instrumental para crear karaokes. Usa **correlación espectral (mel-spectrograma)** con verificación multi-ventana, con fallback por onsets inteligentes y correlación de ondas legacy.

---

## Instalación

```bash
# Prerrequisitos
sudo apt install python3 python3-pip python3-venv ffmpeg

# Setup automático
chmod +x setup.sh
./setup.sh
```

---

## Uso

```bash
# Activar entorno virtual primero
source venv/bin/activate

# Sincronizar (método automático recomendado)
python sync_audio.py --vocal "audio/vocal.flac" --instrumental "audio/instrumental.flac"

# Forzar método específico
python sync_audio.py --vocal vocal.flac --instrumental instrumental.flac --method cross_correlation
python sync_audio.py --vocal vocal.flac --instrumental instrumental.flac --method onset

# Directorio de salida personalizado
python sync_audio.py --vocal vocal.flac --instrumental instrumental.flac --output mis_resultados
```

O usa el script simplificado (espera archivos en `audio/vocal.m4a` y `audio/instrumental.m4a`):

```bash
./sincronizar.sh
```

El resultado se guarda en `output/vocal_sincronizado.m4a`.

---

## Métodos de sincronización

| Método | Descripción | Cuándo usarlo |
|--------|-------------|---------------|
| `auto` (default) | Pipeline en cascada: espectral → onsets → legacy | Siempre, elige el mejor |
| `cross_correlation` | Correlación de ondas legacy con pre-procesamiento | Fallback manual |
| `onset` | Matching de onsets por proximidad | Canciones con ritmos muy marcados |

### Pipeline `auto`:

1. **Correlación espectral** — Convierte a mel-spectrograma (128 bandas) y correlaciona el contenido frecuencial. Verifica en 3 ventanas (0-30s, 30-60s, 60-90s). Si el offset es consistente (std < 0.5s) y la confianza es suficiente, lo acepta.
2. **Onsets inteligentes** — Si el método espectral falla, busca correspondencia entre onsets vocales e instrumentales usando proximity matching con filtro IQR (no asume 1:1).
3. **Correlación legacy** — Último recurso: correlación de ondas con pre-procesamiento (bandpass 80-8kHz) y offset limitado.

---

## Cómo funciona

1. **Carga** ambos audios con librosa (44.1kHz, preservando estéreo)
2. **Pre-procesa** con filtro pasa-bandas 80-8000Hz y normalización RMS (elimina ruido de baja frecuencia que confunde la correlación)
3. **Detecta el offset** usando el pipeline en cascada
4. **Aplica el ajuste**: si el vocal está adelantado, corta del inicio; si está retrasado, añade silencio
5. **Normaliza** de forma conservadora (98% del pico máximo)
6. **Guarda** como M4A (AAC 256kbps) vía FFmpeg
7. **Copia metadatos** del archivo original y agrega "(Sincronizado)" al título

---

## Estructura del proyecto

```
Sync songs/
├── sync_audio.py          # Script principal
├── setup.sh               # Instalación de dependencias
├── sincronizar.sh         # Script de ejecución simplificada
├── requirements.txt       # Dependencias Python
├── README.md              # Esta documentación
├── LICENSE                # Licencia MIT
├── .gitignore             # Exclusiones Git
├── audio/                 # Archivos de entrada
│   ├── vocal.flac
│   └── instrumental.flac
├── output/                # Resultados
│   └── vocal_sincronizado.m4a
└── venv/                  # Entorno virtual Python
```

---

## Troubleshooting

### Se añade silencio incorrecto

El método `auto` (espectral multi-ventana) está diseñado para evitar esto. Si ocurre:

```bash
# Ver qué detecta cada método
python sync_audio.py --vocal vocal.flac --instrumental instrumental.flac --method cross_correlation
python sync_audio.py --vocal vocal.flac --instrumental instrumental.flac --method onset
```

**Causas comunes:**
- El instrumental tiene una intro larga (es normal, el script lo detecta)
- Los archivos no son de la misma canción
- Una pista tiene cambios de tempo respecto a la otra

### El offset parece muy grande

El script permite offsets de hasta ±30s. Si el offset supera eso y no son la misma canción, revisa las duraciones:

```bash
ffprobe -v error -show_entries format=duration audio/vocal.flac
ffprobe -v error -show_entries format=duration audio/instrumental.flac
```

### FFmpeg no encontrado

```bash
sudo apt install ffmpeg
```

### Error de dependencias

```bash
./setup.sh
```

---

## Dependencias

- `librosa` — carga de audio, mel-espectrogramas, onsets
- `soundfile` — escritura WAV
- `numpy` — cálculos numéricos
- `scipy` — correlación cruzada, filtros butter
- `mutagen` — metadatos de audio
- `FFmpeg` — conversión a M4A/AAC
