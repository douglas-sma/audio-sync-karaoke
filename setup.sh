#!/bin/bash

echo "=== CONFIGURACIÓN DEL SINCRONIZADOR DE AUDIO ==="
echo

# Verificar si Python está instalado
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 no está instalado. Instálalo con:"
    echo "sudo apt update && sudo apt install python3 python3-pip"
    exit 1
fi

# Verificar si FFmpeg está instalado
if ! command -v ffmpeg &> /dev/null; then
    echo "🔧 Instalando FFmpeg..."
    sudo apt update
    sudo apt install -y ffmpeg
fi

# Crear entorno virtual si no existe
if [ ! -d "venv" ]; then
    echo "🐍 Creando entorno virtual Python..."
    python3 -m venv venv
fi

# Activar entorno virtual e instalar dependencias
echo "📦 Instalando dependencias de Python..."
source venv/bin/activate
pip install -r requirements.txt
deactivate

echo
echo "✅ Configuración completada!"
echo
echo "=== CÓMO USAR ==="
echo "Para sincronizar tus archivos de audio:"
echo
echo "python3 sync_audio.py --vocal audio/audio.mp3 --instrumental audio/instrumental.mp3"
echo
echo "Opciones adicionales:"
echo "  --output DIRECTORIO    : Directorio donde guardar los resultados (default: output)"
echo "  --method MÉTODO        : cross_correlation (default) o onset"
echo
echo "Ejemplo completo:"
echo "python3 sync_audio.py --vocal audio/audio.mp3 --instrumental audio/instrumental.mp3 --output mi_karaoke"
echo
