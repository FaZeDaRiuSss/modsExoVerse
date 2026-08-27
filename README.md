# 🌌 ExoVerse Mod Pack

Modpack oficial del servidor **ExoVerse** (Minecraft **1.20.1 · Forge**).

Este repositorio contiene los mods oficiales del servidor y el manifiesto de
versiones que utiliza el **ExoVerse Mod Updater**.

---

## 🎮 Para jugadores

1. Descarga `ExoVerseUpdater.exe` desde el servidor de Discord / web de ExoVerse.
2. Ejecútalo. El programa:
   - localiza tu carpeta de mods automáticamente (`%APPDATA%\.minecraft\mods`);
   - comprueba si tu instalación está al día;
   - descarga, actualiza o elimina **solo** los mods gestionados por ExoVerse
     (tus mods personales nunca se tocan);
   - verifica cada archivo con SHA-256 antes de instalarlo;
   - y si algo falla, restaura tu versión anterior.
3. Cuando diga **"Tu instalación está actualizada"**, abre Minecraft y ¡a jugar!

> ⚠️ Cierra Minecraft antes de actualizar los mods.
> No necesitas instalar Git, Python ni nada más.

---

## 🛠 Para el administrador (cómo actualizar el pack)

El updater es compatible con **dos formas de distribuir los mods** — él mismo
lee el campo `"dist"` del `manifest.json` y se adapta. Tú eliges el modo al
generar el manifiesto:

**Opción 1 — Modo carpeta (el que usas ahora): los `.jar` se suben a `mods/`**

```bash
# Desde la raíz del repositorio:
python ExoVerseUpdater.py --build-manifest --src-folder mods

# O si los mods están en la carpeta actual (por ejemplo, dentro de una
# instancia del launcher): el propio updater y el README se omiten solos
python ExoVerseUpdater.py --build-manifest --src-folder . --out-manifest ..\manifest.json
```

Subes la carpeta `mods/` con los jars + `manifest.json`. El generador te
avisará si algún jar supera los 100 MB (límite de GitHub).

**Opción 2 — Modo zip: un único `mods.zip`** (si algún mod no cabe en GitHub)

```bash
python ExoVerseUpdater.py --build-manifest --src-folder mods --zip
```

Subes `mods.zip` + `manifest.json`. El updater descarga el zip y extrae
solo lo que ha cambiado, verificando cada archivo.

Para cambiar de modo: regenérate el manifiesto con o sin `--zip` y sube lo
que corresponda. El programa de los jugadores detecta el modo automáticamente
y nunca mezcla ambos.

3. Sube los cambios:

   ```bash
   git add mods.zip manifest.json     # o: git add mods manifest.json
   git commit -m "Pack vX.Y.Z"
   git push origin main
   ```

4. Los jugadores verán la actualización la próxima vez que abran el updater.

### Reglas importantes

- **No edites `manifest.json` a mano**: siempre se genera con
  `--build-manifest` (contiene el SHA-256 de cada archivo y del zip).
- El updater ignora cualquier archivo que no esté en el manifiesto
  (incluidas rutas maliciosas) y verifica cada mod con SHA-256 antes de
  instalarlo.
- **Límite de GitHub**: ningún archivo puede superar los 100 MB. En modo
  carpeta el generador te avisa; en modo zip, si `mods.zip` supera 100 MB
  usa Releases (permite hasta 2 GB) — pídelo y añado el soporte.

### Estructura del repositorio (modo carpeta)

```
modsExoVerse/
├── README.md          ← este archivo
├── manifest.json      ← GENERADO (no editar a mano)
└── mods/
    ├── alexsmobs-1.22.6.jar
    ├── jei-15.2.0.27.jar
    └── (subcarpetas opcionales)
        └── optimizacion/
            └── ferritecore.jar
```

---

## 🐛 ¿Problemas?

El updater guarda un registro de actividad en:

```
%LOCALAPPDATA%\ExoVerseUpdater\exoverse_updater.log
```

Si algo falla, envía ese archivo al equipo de ExoVerse.
