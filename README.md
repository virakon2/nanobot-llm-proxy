# LLM Key Rotation Proxy

Una aplicación web local que actúa como proxy OpenAI-compatible para rotar automáticamente entre múltiples API keys (Gemini, OpenRouter, Nvidia).

## Instalación y Uso

1. Ejecuta el archivo `start_proxy.bat` (o simplemente corre `python gemini_proxy.py`).
2. El servidor proxy se iniciará en `http://localhost:19090`.
3. Abre esta dirección en tu navegador web para acceder a la interfaz y agregar tus propias API keys. Toda la información se guarda localmente.

## Integración con Nanobot

Para utilizar este proxy rotador dentro de **Nanobot**, necesitas modificar tu archivo `config.json` para definir un proveedor `custom` que apunte al proxy local.

1. Abre tu `config.json` (usualmente en `~/.nanobot/config.json`).
2. Configura el proveedor `custom` apuntando a `http://localhost:19090` y activa el uso por defecto:

```json
{
  "providers": {
    "custom": {
      "apiKey": "rotation-proxy",
      "apiBase": "http://localhost:19090",
      "extraHeaders": null
    }
  },
  "agents": {
    "defaults": {
      "provider": "custom"
    }
  }
}
```

> **Nota importante sobre el campo `"model"`:** Aunque este proxy sobrescriba el modelo final (si usas OpenRouter o Nvidia), es **obligatorio** tener definido un `"model"` válido (ej. `"model": "gemini/gemini-2.5-flash"`) dentro de tu bloque `"defaults"` o en la configuración de la clave en el `config.json`. La librería interna de Nanobot exige este parámetro para arrancar la petición con éxito antes de delegarla al proxy.

3. Reinicia Nanobot para que reconozca los cambios y empiece a rutear las peticiones por medio del rotador de claves.
