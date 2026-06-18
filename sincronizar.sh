#!/bin/bash

echo "🎵 SINCRONIZADOR DE KARAOKE 🎤"
echo "=============================="
echo

# Verificar que los archivos existen
if [ ! -f "audio/vocal.m4a" ]; then
    echo "❌ Error: No se encuentra audio/vocal.m4a"
    exit 1
fi

if [ ! -f "audio/instrumental.m4a" ]; then
    echo "❌ Error: No se encuentra audio/instrumental.m4a"
    exit 1
fi

echo "✅ Archivos encontrados:"
echo "   - Vocal: audio/vocal.m4a"
echo "   - Instrumental: audio/instrumental.m4a"
echo

# Verificar que el entorno virtual existe
if [ ! -d "venv" ]; then
    echo "❌ Error: Entorno virtual no encontrado. Ejecuta primero: ./setup.sh"
    exit 1
fi

# Ejecutar sincronización
echo "🔄 Iniciando sincronización..."
source venv/bin/activate
python sync_audio.py --vocal audio/vocal.m4a --instrumental audio/instrumental.m4a --output karaoke_output
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
