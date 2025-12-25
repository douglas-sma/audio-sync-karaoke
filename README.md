# 🎵 Audio Sync Pro - Sincronizador de Audio para Karaoke

<div align="center">

![Python](https://img.shields.io/badge/Python-3.7+-blue.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)
![Platform](https://img.shields.io/badge/Platform-Linux%20%7C%20macOS%20%7C%20Windows-lightgrey.svg)
![Status](https://img.shields.io/badge/Status-Production%20Ready-brightgreen.svg)

**Sincroniza perfectamente audio vocal con instrumental usando algoritmos avanzados de correlación cruzada**

[🚀 Instalación](#-instalación-rápida) • [📖 Uso](#-uso) • [✨ Características](#-características) • [🛠️ Configuración](#️-configuración-avanzada)

</div>

---

## 🎯 ¿Qué hace Audio Sync Pro?

**Audio Sync Pro** es una herramienta profesional que detecta automáticamente el desfase temporal entre un audio vocal y su instrumental, aplicando la corrección necesaria para lograr una sincronización perfecta. Ideal para crear karaoke de calidad profesional.

### 🔥 Problema que resuelve:
- ✅ Audio vocal y instrumental desincronizados
- ✅ Diferentes puntos de inicio entre archivos
- ✅ Necesidad de ajuste manual tedioso
- ✅ Pérdida de calidad en el proceso

### 🎯 Resultado:
- 🎵 **Sincronización perfecta** - Precisión de milisegundos
- 🔊 **Calidad preservada** - Sin pérdida de frecuencias ni volumen
- 🎤 **Listo para karaoke** - Suenan como un solo audio
- ⚡ **Proceso automático** - Sin ajuste manual necesario

---

## ✨ Características

| Característica | Descripción |
|---|---|
| 🎯 **Detección Automática** | Algoritmo de correlación cruzada para máxima precisión |
| 🔊 **Preservación de Calidad** | Mantiene frecuencias originales y rango dinámico |
| 🎵 **Soporte Estéreo/Mono** | Funciona con cualquier formato de canal |
| ⚡ **Procesamiento Rápido** | Análisis optimizado de primeros 60 segundos |
| 🎤 **Calidad Profesional** | Salida en WAV 24-bit y MP3 320kbps |
| 🔧 **Fácil de Usar** | Un solo comando para todo el proceso |

---

## 🚀 Instalación Rápida

### Prerrequisitos
```bash
# Ubuntu/Debian
sudo apt update && sudo apt install python3 python3-pip python3-venv ffmpeg

# macOS (con Homebrew)
brew install python ffmpeg

# Windows (con Chocolatey)
choco install python ffmpeg
```

### Instalación
```bash
# 1. Clonar el repositorio
git clone https://github.com/tu-usuario/audio-sync-pro.git
cd audio-sync-pro

# 2. Configurar automáticamente
chmod +x setup.sh
./setup.sh
```

---

## 📖 Uso

### 🎵 Uso Simple (Recomendado)
```bash
# 1. Coloca tus archivos en la carpeta audio/
cp tu_vocal.mp3 audio/audio.mp3
cp tu_instrumental.mp3 audio/instrumental.mp3

# 2. ¡Sincronizar!
./sincronizar.sh
```

### ⚙️ Uso Avanzado
```bash
# Activar entorno virtual
source venv/bin/activate

# Sincronización personalizada
python sync_audio.py --vocal mi_vocal.mp3 --instrumental mi_instrumental.mp3 --output mi_resultado

# Usar método alternativo
python sync_audio.py --vocal audio.mp3 --instrumental instrumental.mp3 --method onset

# Desactivar entorno virtual
deactivate
```

---

## 📁 Estructura del Proyecto

```
audio-sync-pro/
├── 📁 audio/                    # Carpeta para tus archivos de audio
│   ├── audio.mp3               # Tu archivo vocal (colocar aquí)
│   ├── instrumental.mp3        # Tu archivo instrumental (colocar aquí)
│   └── .gitkeep               # Mantiene la carpeta en Git
├── 📁 karaoke_output/          # Archivos sincronizados (se crea automáticamente)
│   ├── vocal_sincronizado.wav  # Resultado en alta calidad
│   └── vocal_sincronizado.mp3  # Resultado en MP3
├── 🐍 venv/                    # Entorno virtual Python
├── 🎵 sync_audio.py            # Script principal
├── 🚀 setup.sh                 # Configuración automática
├── ⚡ sincronizar.sh           # Ejecución simple
├── 📋 requirements.txt         # Dependencias Python
├── 📖 README.md                # Esta documentación
└── 🙈 .gitignore              # Archivos a ignorar en Git
```

---

## 🔬 Cómo Funciona

### 1. 🎯 **Análisis de Correlación Cruzada**
El algoritmo analiza las formas de onda de ambos audios para encontrar el punto de máxima similitud, determinando el offset exacto.

### 2. ⚡ **Ajuste Temporal**
- **Vocal adelantado**: Corta silencio del inicio
- **Vocal retrasado**: Agrega silencio al inicio
- **Ya sincronizado**: No modifica nada

### 3. � **Preservación de Calidad**
- Mantiene formato estéreo original
- Preserva todas las frecuencias
- Normalización mínima (98% del volumen original)

### 4. 💾 **Salida de Alta Calidad**
- **WAV**: 24-bit, sin compresión
- **MP3**: 320kbps, máxima calidad

---

## 🛠️ Configuración Avanzada

### Opciones del Script Principal

| Parámetro | Descripción | Ejemplo |
|---|---|---|
| `--vocal` | Archivo de audio vocal | `--vocal mi_vocal.mp3` |
| `--instrumental` | Archivo instrumental | `--instrumental mi_instrumental.mp3` |
| `--output` | Directorio de salida | `--output mis_resultados` |
| `--method` | Método de sincronización | `--method cross_correlation` |

### Métodos de Sincronización

#### 🎯 **Cross Correlation** (Recomendado)
- Máxima precisión
- Funciona con cualquier tipo de audio
- Tiempo de procesamiento medio

#### 🎵 **Onset Detection**
- Basado en detección de inicios musicales
- Más rápido
- Mejor para música con ritmos marcados

---

## 🎤 Ejemplos de Uso

### Karaoke Básico
```bash
# Sincronizar vocal con instrumental
./sincronizar.sh

# Resultado: vocal perfectamente sincronizado
# Usar en tu software de karaoke favorito
```

### Producción Musical
```bash
# Sincronizar múltiples tomas vocales
python sync_audio.py --vocal toma1.wav --instrumental base.wav --output sync_toma1
python sync_audio.py --vocal toma2.wav --instrumental base.wav --output sync_toma2

# Ahora todas las tomas están sincronizadas con la base
```

### Procesamiento por Lotes
```bash
# Script personalizado para múltiples archivos
for vocal in vocals/*.mp3; do
    nombre=$(basename "$vocal" .mp3)
    python sync_audio.py --vocal "$vocal" --instrumental instrumental.mp3 --output "sync_$nombre"
done
```

---

## � Solución de Problemas

### ❌ Error: "ModuleNotFoundError"
```bash
# Reinstalar dependencias
./setup.sh
```

### ❌ Error: "FFmpeg no encontrado"
```bash
# Ubuntu/Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg

# Windows
# Descargar desde: https://ffmpeg.org/download.html
```

### ❌ Sincronización inexacta
```bash
# Probar método alternativo
python sync_audio.py --vocal audio.mp3 --instrumental instrumental.mp3 --method onset

# Verificar que ambos archivos sean de la misma canción
# Asegurar que no haya demasiado silencio al inicio
```

### 🔊 Volumen bajo en resultado
✅ **Ya resuelto** - La versión actual preserva el volumen original perfectamente

---

## 📊 Especificaciones Técnicas

| Aspecto | Especificación |
|---|---|
| **Formatos Soportados** | MP3, WAV, FLAC, AAC, M4A, OGG |
| **Calidad de Salida** | WAV 24-bit, MP3 320kbps |
| **Sample Rate** | 44.1 kHz (CD Quality) |
| **Canales** | Mono y Estéreo |
| **Precisión** | Nivel de muestra (≈0.023ms a 44.1kHz) |
| **Algoritmo** | Correlación cruzada + detección de onset |

---

## 🚀 Roadmap

- [ ] 🎵 Interfaz gráfica (GUI)
- [ ] 📱 App móvil
- [ ] 🎛️ Ajuste de ganancia automático
- [ ] 🔄 Procesamiento por lotes
- [ ] 🎚️ Ecualizador integrado
- [ ] 🌐 Versión web
- [ ] 🎸 Detección de instrumentos
- [ ] 🎤 Separación de voces automática

---

## 🤝 Contribuir

¡Las contribuciones son bienvenidas! 

1. Fork el proyecto
2. Crea tu rama de características (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

---

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Ver `LICENSE` para más detalles.

---

## 👨‍💻 Autor

Creado con ❤️ para la comunidad de karaoke y producción musical.

---

## � ¡Disfruta tu Karaoke Perfecto!

<div align="center">

**¿Te gustó Audio Sync Pro? ¡Dale una ⭐ al repositorio!**

[⬆️ Volver arriba](#-audio-sync-pro---sincronizador-de-audio-para-karaoke)

</div>
