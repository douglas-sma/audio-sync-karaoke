#!/bin/bash

echo "🎵 SINCRONIZADOR DE KARAOKE 🎤"
echo "=============================="
echo

# Verificar que los archivos existen
if [ ! -f "audio/audio.mp3" ]; then
    echo "❌ Error: No se encuentra audio/audio.mp3"
    exit 1
fi

if [ ! -f "audio/instrumental.mp3" ]; then
    echo "❌ Error: No se encuentra audio/instrumental.mp3"
    exit 1
fi

echo "✅ Archivos encontrados:"
echo "   - Vocal: audio/audio.mp3"
echo "   - Instrumental: audio/instrumental.mp3"
echo

# Verificar que el entorno virtual existe
if [ ! -d "venv" ]; then
    echo "❌ Error: Entorno virtual no encontrado. Ejecuta primero: ./setup.sh"
    exit 1
fi

# Ejecutar sincronización
echo "🔄 Iniciando sincronización..."
source venv/bin/activate
python sync_audio.py --vocal audio/audio.mp3 --instrumental audio/instrumental.mp3 --output karaoke_output
deactivate

if [ $? -eq 0 ]; then
    echo
    echo "🎉 ¡SINCRONIZACIÓN COMPLETADA!"
    echo "📁 Archivo generado en: karaoke_output/"
    echo
    echo "Archivo creado:"
    echo "  - vocal_sincronizado.wav/mp3     : Tu audio vocal sincronizado"
    echo
    echo "💡 Este vocal ya está perfectamente sincronizado con tu instrumental"
else
    echo "❌ Error durante la sincronización"
fi
