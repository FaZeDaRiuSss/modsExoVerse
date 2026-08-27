#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
═══════════════════════════════════════════════════════════════════════════════
 EXOVERSE MOD UPDATER  ·  Minecraft 1.20.1 · Forge
═══════════════════════════════════════════════════════════════════════════════
 Actualizador / instalador de mods para los jugadores del servidor ExoVerse.

 Características principales:
   • Fuente oficial: repositorio de GitHub (manifiesto + carpeta mods/).
   • Sin dependencias externas: solo biblioteca estándar de Python (tkinter
     incluido en la instalación estándar de Windows).
   • Detección rápida de cambios mediante manifiesto con SHA-256 (sin
     descargar el repositorio completo, sin Git, sin Python en el PC del jugador).
   • Instalación limpia, actualización selectiva, eliminación segura de mods
     gestionados, reparación, rollback transaccional y backups deltas.
   • Interfaz gráfica moderna (tkinter) con tema oscuro "ExoVerse".
   • Preparado para compilar a .exe con PyInstaller (--onefile --windowed).

 Uso por parte del administrador (tú):
   python ExoVerseUpdater.py --build-manifest --src-folder mods [--new-version 1.4.2]
   (desde la raíz del repositorio; o --src-folder . si los mods están en la
    carpeta actual — el propio updater y el README se omiten automáticamente)

   El updater es compatible con DOS modos de distribución (los detecta en el
   campo "dist" del manifest.json, generado automáticamente):
     • Modo carpeta (por defecto): los .jar se suben a mods/ del repositorio.
       python ExoVerseUpdater.py --build-manifest --src-folder mods
     • Modo zip: un solo archivo mods.zip (útil si GitHub rechaza algún jar
       por superar 100 MB).
       python ExoVerseUpdater.py --build-manifest --src-folder mods --zip
   Para cambiar de modo: regenérate el manifiesto con/sin --zip y sube lo
   que corresponda (mods/ o mods.zip).

 Uso de prueba / diagnóstico (sin interfaz):
   python ExoVerseUpdater.py --headless [--apply] [--source-url URL] [--mods-folder DIR]

═══════════════════════════════════════════════════════════════════════════════
"""

# ---------------------------------------------------------------------------
# 0. IMPORTS  (solo biblioteca estándar)
# ---------------------------------------------------------------------------
import argparse
import base64
import ctypes
import datetime
import glob
import hashlib
import json
import logging
import logging.handlers
import math
import os
import queue
import random
import re
import shutil
import socket
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# 1. CONFIGURACIÓN CENTRALIZADA
#    (único lugar donde cambias los datos del repositorio / del pack)
# ---------------------------------------------------------------------------
CONFIG: Dict[str, Any] = {
    # ── Repositorio oficial (fuente de verdad) ──────────────────────────
    "github_owner": "FaZeDaRiuSss",
    "github_repo": "modsExoVerse",
    "github_branch": "main",

    # ── Datos del pack ──────────────────────────────────────────────────
    "pack_name": "ExoVerse",
    "minecraft_version": "1.20.1",
    "loader": "Forge",

    # ── Rutas dentro del repositorio ────────────────────────────────────
    "manifest_path": "manifest.json",   # manifiesto en la raíz del repo
    "mods_subfolder": "mods",           # carpeta con los .jar dentro del repo

    # ── Comportamiento ──────────────────────────────────────────────────
    "max_parallel_downloads": 3,        # descargas simultáneas (2-4 recomendado)
    "timeout_seconds": 25,              # timeout de red por petición
    "retries": 3,                       # reintentos ante errores de red
    "backoff_base": 1.5,                # espera entre reintentos (segundos)
    "manifest_max_bytes": 20 * 1024 * 1024,  # tope de seguridad del manifiesto
    "backup_keep_generations": 1,       # backups delta a conservar tras éxito
    "disk_margin_factor": 1.15,         # margen de espacio libre requerido
    "disk_margin_bytes": 50 * 1024 * 1024,

    # ── Identidad de la app ─────────────────────────────────────────────
    "app_name": "ExoVerse Mod Updater",
    "app_version": "1.0.0",
    "local_manifest_name": ".exoverse_manifest.json",
    "staging_dir_name": ".exoverse_staging",
}

# Tema visual (también centralizado)
THEME: Dict[str, str] = {
    "bg": "#0d1220",          # fondo general (azul espacial profundo)
    "card": "#151d31",        # tarjetas
    "card_border": "#232f4d",
    "accent": "#5b7cfa",      # azul ExoVerse
    "accent_hover": "#6f8dff",
    "accent_dark": "#3d5bd6",
    "text": "#e8ecf8",
    "muted": "#8b96b0",
    "ok": "#3ddc84",
    "warn": "#ffb454",
    "err": "#ff6b6b",
    "info": "#7aa2ff",
}

# Icono de la aplicación incrustado (PNG 128x128, base64) — generado con Pillow.
ICON_B64 = "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"

# ---------------------------------------------------------------------------
# 2. ERRORES CONTROLADOS  (código + mensaje amigable)
# ---------------------------------------------------------------------------
class UpdaterError(Exception):
    """Error controlado del updater, con código y mensaje para el jugador."""
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


def friendly_errors() -> Dict[str, str]:
    return {
        "NETWORK":      "No se puede conectar con GitHub. Comprueba tu conexión a Internet e inténtalo de nuevo.",
        "OFFLINE":      "No se puede conectar con GitHub. Comprueba tu conexión a Internet e inténtalo de nuevo.",
        "HTTP_404_MANIFEST": "El repositorio no contiene el archivo manifest.json.\nAvisa al administrador del servidor.",
        "HTTP_404_FILE":     "No se encontró un archivo en el repositorio. Es posible que se haya eliminado.\nAvisa al administrador del servidor.",
        "HTTP_403":     "GitHub ha limitado el número de peticiones.\nEspera unos minutos y vuelve a intentarlo.",
        "HTTP_OTHER":   "GitHub ha devuelto un error inesperado. Inténtalo de nuevo más tarde.",
        "MANIFEST_INVALID": "El manifiesto del repositorio no es válido.\nAvisa al administrador del servidor.",
        "MANIFEST_LOCAL_CORRUPT": "El registro local de ExoVerse está dañado. Se conservarán tus mods y se reconstruirá la instalación.",
        "FOLDER_NOT_FOUND": "No se ha encontrado la carpeta de mods de Minecraft.\nSelecciónala manualmente con el botón «Cambiar carpeta…».",
        "FOLDER_NOT_WRITABLE": "No se puede escribir en la carpeta de mods.\nComprueba los permisos de la carpeta e inténtalo de nuevo.",
        "FOLDER_NOT_DIR": "La ruta seleccionada no es una carpeta válida.",
        "DISK_FULL":    "No hay espacio suficiente en disco para la actualización.\nLibera espacio e inténtalo de nuevo.",
        "PERMISSION":   "No se pudo escribir un archivo. Comprueba los permisos de la carpeta de mods.",
        "FILE_LOCKED":  "Un archivo está en uso (¿tienes Minecraft abierto?).\nCierra Minecraft e inténtalo de nuevo.",
        "HASH_MISMATCH":"La descarga de un archivo no es válida (no coincide con el oficial).\nSe conservó tu versión anterior. Pulsa Reintentar.",
        "SIZE_MISMATCH":"La descarga de un archivo se interrumpió o llegó incompleta.\nSe conservó tu versión anterior. Pulsa Reintentar.",
        "ARCHIVE_INVALID":   "El archivo mods.zip del repositorio no es válido (contenido alterado o corrupto).\nAvisa al administrador del servidor.",
        "ARCHIVE_INCOMPLETE":"El archivo mods.zip está incompleto (faltan archivos del pack).\nAvisa al administrador del servidor.",
        "CANCELLED":    "Actualización cancelada. No se ha modificado nada.",
        "APPLY_FAILED": "No se pudo aplicar la actualización. Se ha restaurado tu versión anterior.",
        "UNSAFE_PATH":  "El repositorio contiene rutas no permitidas y se han ignorado.\nAvisa al administrador del servidor.",
        "UNKNOWN":      "Ocurrió un error inesperado. Revisa el archivo exoverse_updater.log.",
    }


# ---------------------------------------------------------------------------
# 3. UTILIDADES
# ---------------------------------------------------------------------------
def hsize(n: float) -> str:
    """Formatea bytes de forma legible: 12.4 MB, 1.84 GB…"""
    n = max(0.0, float(n))
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(n)} {unit}"
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} TB"


def parse_version(v: Optional[str]) -> Tuple:
    """'1.4.2' → (1, 4, 2). Segmentos numéricos se comparan como números."""
    if not v:
        return (0,)
    parts = []
    for seg in str(v).strip().split("."):
        seg = seg.strip()
        m = re.match(r"^(\d+)(.*)$", seg)
        if m:
            parts.append(int(m.group(1)))
            if m.group(2):
                parts.append(m.group(2))   # p.ej. 'beta'
        else:
            parts.append(seg)
    return tuple(parts)


def version_greater(a: Optional[str], b: Optional[str]) -> bool:
    return parse_version(a) > parse_version(b)


def bump_version(v: str) -> str:
    """Incrementa la parte final numérica: 1.4.2 → 1.4.3."""
    m = re.match(r"^(\d+(?:\.\d+)*)$", v.strip())
    if m:
        parts = [int(p) for p in v.strip().split(".")]
        parts[-1] += 1
        return ".".join(str(p) for p in parts)
    m2 = re.match(r"^(\d+(?:\.\d+)*)(\D.*)$", v.strip())
    if m2:
        return bump_version(m2.group(1))
    return "1.0.0"


def iso_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_file(path: str, progress_cb: Optional[Callable[[int, int], None]] = None,
                cancel_event: Optional[threading.Event] = None) -> str:
    h = hashlib.sha256()
    total = os.path.getsize(path)
    done = 0
    with open(path, "rb") as f:
        while True:
            if cancel_event is not None and cancel_event.is_set():
                raise UpdaterError("CANCELLED", friendly_errors()["CANCELLED"])
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
            done += len(chunk)
            if progress_cb:
                progress_cb(done, total)
    return h.hexdigest()


def safe_join(base: str, relpath: str) -> Optional[str]:
    """
    Combina base + ruta relativa validando que el resultado NO salga de base.
    Rechaza: rutas absolutas, '..', letras de unidad, backslashes, bytes nulos.
    """
    if not relpath or "\x00" in relpath:
        return None
    rel = relpath.replace("\\", "/")
    if rel.startswith("/"):
        return None
    if ":" in rel.split("/")[0]:
        return None                       # p.ej. 'C:/Windows/...'
    segs = rel.split("/")
    if any(s in ("..", ".", "") for s in segs):
        return None
    dest = os.path.join(base, *segs)
    # Comprobación final a prueba de balas (rutas reales resueltas):
    try:
        base_r = os.path.normcase(os.path.realpath(base))
        dest_r = os.path.normcase(os.path.realpath(dest))
        if dest_r != base_r and not dest_r.startswith(base_r + os.sep):
            return None
    except Exception:
        return None
    return dest


def atomic_write(path: str, data: bytes) -> None:
    """Escritura atómica: tmp + os.replace (nunca deja el archivo a medias)."""
    tmp = path + ".tmp"
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def atomic_write_json(path: str, obj: Any) -> None:
    atomic_write(path, json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8"))


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def open_in_explorer(path: str) -> None:
    if os.name == "nt":
        os.startfile(path)  # type: ignore[attr-defined]  # solo Windows
    else:
        webbrowser.open("file://" + os.path.abspath(path))


# ---------------------------------------------------------------------------
# 4. LOGGING  (exoverse_updater.log, con rotación)
# ---------------------------------------------------------------------------
LOG = logging.getLogger("exoverse")
LOG.setLevel(logging.INFO)


def setup_logging(log_path: str, console: bool = False) -> None:
    try:
        ensure_dir(os.path.dirname(log_path))
        handler = logging.handlers.RotatingFileHandler(
            log_path, maxBytes=1024 * 1024, backupCount=2, encoding="utf-8")
        handler.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))
        LOG.addHandler(handler)
    except Exception as e:  # el logging nunca debe tumbar la app
        print(f"aviso: no se pudo abrir el log: {e}", file=sys.stderr)
    if console and sys.stdout is not None:
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
        LOG.addHandler(ch)


# ---------------------------------------------------------------------------
# 5. RUTAS DE LA APLICACIÓN Y CONFIGURACIÓN DEL USUARIO
# ---------------------------------------------------------------------------
class AppPaths:
    """Rutas persistentes. NUNCA se usa __file__: cuando el .exe se ejecuta
    desde cualquier sitio, los datos van a %LOCALAPPDATA% (escritura segura)."""

    @staticmethod
    def app_data_dir() -> str:
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA") \
            or os.path.expanduser("~")
        d = os.path.join(base, "ExoVerseUpdater")
        ensure_dir(d)
        return d

    @staticmethod
    def config_file() -> str:
        return os.path.join(AppPaths.app_data_dir(), "config.json")

    @staticmethod
    def log_file() -> str:
        return os.path.join(AppPaths.app_data_dir(), "exoverse_updater.log")

    @staticmethod
    def backups_root() -> str:
        return os.path.join(AppPaths.app_data_dir(), "backups")


class UserConfig:
    """Configuración persistente del jugador (carpeta de mods elegida, etag…)."""

    DEFAULTS: Dict[str, Any] = {
        "mods_folder": None,
        "manifest_etag": None,
        "last_known_version": None,
    }

    def __init__(self) -> None:
        self.data: Dict[str, Any] = dict(self.DEFAULTS)
        self._load()

    def _load(self) -> None:
        try:
            with open(AppPaths.config_file(), "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                for k in self.DEFAULTS:
                    if k in loaded:
                        self.data[k] = loaded[k]
        except FileNotFoundError:
            pass
        except Exception as e:
            LOG.warning("config del usuario ilegible (%s); se usan valores por defecto", e)

    def save(self) -> None:
        try:
            atomic_write_json(AppPaths.config_file(), self.data)
        except Exception as e:
            LOG.warning("no se pudo guardar la configuración: %s", e)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.save()


# ---------------------------------------------------------------------------
# 6. MANIFIESTO
#    Formato (generado por --build-manifest, consumido por el updater):
#    {
#      "schema": 1,
#      "name": "ExoVerse",
#      "version": "1.4.2",
#      "minecraft_version": "1.20.1",
#      "loader": "Forge",
#      "generated_at": "2026-08-27T12:00:00Z",
#      "total_size": 123456789,
#      "file_count": 42,
#      "files": {
#        "alexsmobs-1.22.6.jar":        {"size": 15800000, "sha256": "ab12…"},
#        "subcarpeta/jei-15.2.0.27.jar": {"size": 4120000,  "sha256": "cd34…"}
#      }
#    }
# ---------------------------------------------------------------------------
class ManifestError(UpdaterError):
    pass


class ManifestManager:
    SCHEMA = 1

    @staticmethod
    def validate(data: Any) -> Dict[str, Any]:
        """Valida y normaliza un manifiesto remoto. Lanza ManifestError si es inválido."""
        if not isinstance(data, dict):
            raise ManifestError("MANIFEST_INVALID", friendly_errors()["MANIFEST_INVALID"])
        schema = data.get("schema")
        if schema != ManifestManager.SCHEMA:
            raise ManifestError("MANIFEST_INVALID",
                                "El manifiesto del repositorio usa un formato no compatible.\n"
                                "Avisa al administrador del servidor.")
        version = data.get("version")
        if not isinstance(version, str) or not version.strip():
            raise ManifestError("MANIFEST_INVALID", friendly_errors()["MANIFEST_INVALID"])
        files = data.get("files")
        if not isinstance(files, dict):
            raise ManifestError("MANIFEST_INVALID", friendly_errors()["MANIFEST_INVALID"])
        clean: Dict[str, Dict[str, Any]] = {}
        for rel, meta in files.items():
            if not isinstance(rel, str) or not isinstance(meta, dict):
                continue
            size = meta.get("size")
            sha = meta.get("sha256")
            if not isinstance(size, int) or size <= 0:
                continue
            if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", sha):
                continue
            clean[rel] = {"size": size, "sha256": sha.lower()}
        # Modo de distribución: "folder" (carpeta mods/) o "zip" (mods.zip)
        dist = data.get("dist", "folder")
        archive: Optional[str] = None
        archive_size: Optional[int] = None
        archive_sha: Optional[str] = None
        if dist == "zip":
            archive = data.get("archive")
            archive_size = data.get("archive_size")
            archive_sha = data.get("archive_sha256")
            if (not isinstance(archive, str) or not archive.strip()
                    or "/" in archive or "\\" in archive
                    or not isinstance(archive_size, int) or archive_size <= 0
                    or not isinstance(archive_sha, str)
                    or not re.fullmatch(r"[0-9a-fA-F]{64}", archive_sha)):
                raise ManifestError("MANIFEST_INVALID", friendly_errors()["MANIFEST_INVALID"])
        else:
            dist = "folder"
        result = {
            "schema": schema,
            "name": str(data.get("name", CONFIG["pack_name"])),
            "version": version.strip(),
            "minecraft_version": str(data.get("minecraft_version", "")),
            "loader": str(data.get("loader", "")),
            "generated_at": str(data.get("generated_at", "")),
            "total_size": int(data.get("total_size", 0) or 0),
            "file_count": len(clean),
            "dist": dist,
            "files": clean,
        }
        if dist == "zip":
            result["archive"] = archive
            result["archive_size"] = archive_size
            result["archive_sha256"] = archive_sha.lower()
        return result

    # -- Construcción (para el administrador: --build-manifest) ----------
    @staticmethod
    def build(src_folder: str, version: Optional[str],
              existing: Optional[Dict[str, Any]] = None,
              make_zip: bool = False,
              zip_out: Optional[str] = None) -> Dict[str, Any]:
        if not os.path.isdir(src_folder):
            raise UpdaterError(
                "FOLDER_NOT_FOUND",
                f"No se encontró la carpeta «{src_folder}».\n"
                f"Ruta comprobada: {os.path.abspath(src_folder)}\n\n"
                "El comando debe ejecutarse desde la carpeta que CONTIENE «mods»\n"
                "(la raíz del repositorio). Ejemplo:\n"
                "  cd ..\n"
                "  python ExoVerseUpdater.py --build-manifest --src-folder mods\n\n"
                "Si los mods están en la carpeta ACTUAL, usa:\n"
                "  python ExoVerseUpdater.py --build-manifest --src-folder .\n"
                "  (el propio updater, el README y manifest.json se omiten solos)")
        files: Dict[str, Dict[str, Any]] = {}
        total = 0
        entries = []
        # Nombres que NUNCA son mods y se omiten automáticamente:
        script_names = {"exoverseupdater.py", "exoverseupdater.exe"}
        if sys.argv:
            script_names.add(os.path.basename(sys.argv[0]).lower())
        root_meta = {"readme.md", "readme.txt", "readme", "license",
                     "license.txt", "license.md", ".gitignore", ".gitattributes",
                     "manifest.json", "exoverse_icon.png", "exoverse_icon.ico",
                     "exoverse_updater.log"}
        for root, dirs, fnames in os.walk(src_folder):
            # No recorrer carpetas ocultas ni de control (.git, .exoverse…)
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for fn in sorted(fnames):
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, src_folder).replace(os.sep, "/")
                low = fn.lower()
                if low in script_names:
                    print(f"  ⚠ {rel}: es el propio updater, se omite.")
                    continue
                if low == CONFIG["local_manifest_name"].lower() or low.startswith(".exoverse"):
                    continue
                if "/" not in rel and low in root_meta:
                    print(f"  ⚠ {rel}: documentación/meta del repositorio, se omite.")
                    continue
                # Seguridad: ocultos, barras raras y rutas con '..' nunca son mods
                if any(seg.startswith(".") for seg in rel.split("/")):
                    print(f"  ⚠ {rel}: archivo oculto o de control, se omite.")
                    continue
                if "\\" in rel:
                    print(f"  ⚠ {rel}: nombre de archivo no válido, se omite.")
                    continue
                if any(s in ("..", ".", "") for s in rel.split("/")):
                    print(f"  ⚠ {rel}: ruta no válida, se omite.")
                    continue
                entries.append((rel, full))
        entries.sort(key=lambda t: t[0].lower())
        n = len(entries)
        for i, (rel, full) in enumerate(entries, 1):
            size = os.path.getsize(full)
            if size == 0:
                print(f"  ⚠ {rel}: archivo vacío, se omite.")
                continue
            print(f"  [{i}/{n}] {rel}  ({hsize(size)})  → sha256…", end="", flush=True)
            sha = sha256_file(full)
            print(" ok")
            files[rel] = {"size": size, "sha256": sha}
            total += size

        if not files:
            raise UpdaterError("MANIFEST_INVALID",
                               "No se encontraron archivos en la carpeta indicada.")

        if version is None:
            old = (existing or {}).get("version")
            version = bump_version(old) if old else "1.0.0"
            print(f"  Versión nueva (auto): {version}")

        manifest = {
            "schema": ManifestManager.SCHEMA,
            "name": CONFIG["pack_name"],
            "version": version,
            "minecraft_version": CONFIG["minecraft_version"],
            "loader": CONFIG["loader"],
            "generated_at": iso_now(),
            "total_size": total,
            "file_count": len(files),
            "files": files,
        }

        if make_zip:
            zip_dir = os.path.dirname(os.path.abspath(zip_out or "mods.zip"))
            zip_path = os.path.join(zip_dir, "mods.zip")
            print(f"  Empaquetando {len(files)} archivos → {os.path.basename(zip_path)} …")
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED,
                                 compresslevel=6) as z:
                for rel, full in entries:
                    if rel in files:
                        z.write(full, rel)
            zs = os.path.getsize(zip_path)
            manifest.update({
                "dist": "zip",
                "archive": os.path.basename(zip_path),
                "archive_size": zs,
                "archive_sha256": sha256_file(zip_path),
            })
            print(f"  ✔ {os.path.basename(zip_path)}: {hsize(zs)}"
                  f" (descomprimido: {hsize(total)})")
            if zs > 100 * 1024 * 1024:
                print("\n  ⚠ ¡AVISO! mods.zip supera 100 MB: GitHub rechazará la subida.")
                print("    → Recomendado: subirlo como Release (GitHub permite hasta 2 GB).")
                print("    → Alternativa: dividir el pack en varios zips.")
        else:
            manifest["dist"] = "folder"
            big = [rel for rel, m in files.items() if m["size"] > 100 * 1024 * 1024]
            if big:
                print("\n  ⚠ ¡AVISO! Estos archivos superan los 100 MB y GitHub "
                      "rechazará la subida:")
                for rel in big[:6]:
                    print(f"    - {rel}  ({hsize(files[rel]['size'])})")
                print("    → Solución: genera el pack en modo zip con --zip "
                      "(o sube esos mods como Release de GitHub).")

        return manifest

    # -- Manifiesto local (registro de archivos gestionados) --------------
    @staticmethod
    def local_path(mods_folder: str) -> str:
        return os.path.join(mods_folder, CONFIG["local_manifest_name"])

    @staticmethod
    def load_local(mods_folder: str) -> Tuple[Optional[Dict[str, Any]], bool]:
        """
        Devuelve (manifest, corrupto). Si el manifiesto local no existe → (None, False).
        Si existe pero es ilegible/inválido → (None, True): el updater NO borrará
        nada (no puede demostrar propiedad) pero sí podrá instalar/actualizar.
        """
        p = ManifestManager.local_path(mods_folder)
        if not os.path.exists(p):
            return None, False
        try:
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            m = ManifestManager.validate(data)
            m["applied_at"] = data.get("applied_at")
            m["source_version"] = data.get("source_version", m["version"])
            return m, False
        except Exception as e:
            LOG.error("manifiesto local corrupto (%s): %s", p, e)
            return None, True

    @staticmethod
    def save_local(mods_folder: str, remote_manifest: Dict[str, Any]) -> None:
        local = {
            "schema": remote_manifest["schema"],
            "name": remote_manifest["name"],
            "version": remote_manifest["version"],
            "source_version": remote_manifest["version"],
            "minecraft_version": remote_manifest["minecraft_version"],
            "loader": remote_manifest["loader"],
            "applied_at": iso_now(),
            "total_size": remote_manifest["total_size"],
            "file_count": remote_manifest["file_count"],
            "dist": remote_manifest.get("dist", "folder"),
            "archive": remote_manifest.get("archive"),
            "archive_size": remote_manifest.get("archive_size"),
            "archive_sha256": remote_manifest.get("archive_sha256"),
            "files": remote_manifest["files"],
        }
        atomic_write_json(ManifestManager.local_path(mods_folder), local)


# ---------------------------------------------------------------------------
# 7. CLIENTE DE GITHUB (fuente remota)
#    Estrategia elegida: manifest.json + raw.githubusercontent.com
#    • La comprobación cuesta UNA petición pequeña (el manifiesto, KBs).
#    • raw.githubusercontent.com NO consume el rate limit de la API REST.
#    • If-None-Match / ETag: si el manifiesto no cambió → 304, 0 bytes.
#    • Los .jar solo se descargan cuando han cambiado (hash/size distinto).
#    Fallback: API REST Contents (rate limit 60/h) por si raw está bloqueado.
# ---------------------------------------------------------------------------
class RemoteSource:
    def __init__(self, source_url: Optional[str] = None):
        if source_url:
            self.base = source_url.rstrip("/")
            self.use_api_fallback = False
        else:
            self.base = (f"https://raw.githubusercontent.com/{CONFIG['github_owner']}/"
                         f"{CONFIG['github_repo']}/{CONFIG['github_branch']}")
            self.use_api_fallback = True
        self.api_base = (f"https://api.github.com/repos/{CONFIG['github_owner']}/"
                         f"{CONFIG['github_repo']}/contents/")
        self.api_ref = f"?ref={CONFIG['github_branch']}"
        self.timeout = CONFIG["timeout_seconds"]
        self.retries = CONFIG["retries"]
        self._ua = {"User-Agent": f"ExoVerseUpdater/{CONFIG['app_version']}"}

    # -- HTTP bajo nivel --------------------------------------------------
    def _open(self, url: str, headers: Optional[Dict[str, str]] = None) -> Any:
        req_headers = dict(self._ua)
        if headers:
            req_headers.update(headers)
        req = urllib.request.Request(url, headers=req_headers)
        last_err: Optional[Exception] = None
        for attempt in range(self.retries + 1):
            try:
                return urllib.request.urlopen(req, timeout=self.timeout)
            except urllib.error.HTTPError as e:
                # errores HTTP: no reintentar 4xx (salvo 429/5xx)
                if e.code in (429,) or e.code >= 500:
                    last_err = e
                    time.sleep(CONFIG["backoff_base"] * (attempt + 1))
                    continue
                raise
            except (urllib.error.URLError, socket.timeout, ConnectionError, TimeoutError,
                    OSError) as e:
                last_err = e
                if attempt < self.retries:
                    time.sleep(CONFIG["backoff_base"] * (attempt + 1))
                continue
        raise UpdaterError("NETWORK", friendly_errors()["NETWORK"])

    # -- Manifiesto -------------------------------------------------------
    def fetch_manifest(self, etag: Optional[str] = None
                       ) -> Tuple[Optional[Dict[str, Any]], Optional[str], bool]:
        """
        Devuelve (manifest, nuevo_etag, sin_cambios).
        sin_cambios=True → el servidor respondió 304 (el manifiesto es el mismo
        que ya conocemos); manifest será None.
        """
        headers = {}
        if etag:
            headers["If-None-Match"] = etag
        url = f"{self.base}/{CONFIG['manifest_path']}"
        try:
            resp = self._open(url, headers)
        except urllib.error.HTTPError as e:
            if e.code == 304:
                return None, etag, True
            if e.code == 404:
                raise UpdaterError("HTTP_404_MANIFEST", friendly_errors()["HTTP_404_MANIFEST"])
            if e.code == 403:
                raise UpdaterError("HTTP_403", friendly_errors()["HTTP_403"])
            raise UpdaterError("HTTP_OTHER", friendly_errors()["HTTP_OTHER"])
        data = resp.read(CONFIG["manifest_max_bytes"] + 1)
        if len(data) > CONFIG["manifest_max_bytes"]:
            raise ManifestError("MANIFEST_INVALID", friendly_errors()["MANIFEST_INVALID"])
        new_etag = resp.headers.get("ETag")
        try:
            manifest = ManifestManager.validate(json.loads(data.decode("utf-8")))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ManifestError("MANIFEST_INVALID", friendly_errors()["MANIFEST_INVALID"])
        return manifest, new_etag, False

    def fetch_manifest_fallback_api(self, etag: Optional[str] = None
                                    ) -> Tuple[Optional[Dict[str, Any]], Optional[str], bool]:
        """Fallback vía API REST Contents (solo si raw falla y estamos en GitHub)."""
        headers = {"Accept": "application/vnd.github.raw"}
        if etag:
            headers["If-None-Match"] = etag
        url = self.api_base + urllib.parse.quote(CONFIG["manifest_path"]) + self.api_ref
        try:
            resp = self._open(url, headers)
        except urllib.error.HTTPError as e:
            if e.code == 304:
                return None, etag, True
            if e.code == 404:
                raise UpdaterError("HTTP_404_MANIFEST", friendly_errors()["HTTP_404_MANIFEST"])
            if e.code == 403:
                raise UpdaterError("HTTP_403",
                                   "GitHub ha limitado las peticiones (60/h sin autenticar).\n"
                                   "Espera unos minutos y vuelve a intentarlo.")
            raise UpdaterError("HTTP_OTHER", friendly_errors()["HTTP_OTHER"])
        data = resp.read(CONFIG["manifest_max_bytes"] + 1)
        new_etag = resp.headers.get("ETag")
        try:
            manifest = ManifestManager.validate(json.loads(data.decode("utf-8")))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ManifestError("MANIFEST_INVALID", friendly_errors()["MANIFEST_INVALID"])
        return manifest, new_etag, False

    # -- Descarga de archivos ---------------------------------------------
    def _download_to(self, url: str, tmp_path: str,
                     expected_size: int, expected_sha: str,
                     progress_cb: Optional[Callable[[int, int], None]] = None,
                     cancel_event: Optional[threading.Event] = None,
                     context: str = "") -> None:
        """
        Descarga a tmp_path, verifica tamaño + SHA-256 y solo entonces devuelve.
        Cualquier error borra el temporal y lanza UpdaterError.
        """
        try:
            resp = self._open(url)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                extra = f"\nArchivo: {context}" if context else ""
                raise UpdaterError("HTTP_404_FILE",
                                   friendly_errors()["HTTP_404_FILE"] + extra)
            if e.code == 403:
                raise UpdaterError("HTTP_403", friendly_errors()["HTTP_403"])
            raise UpdaterError("HTTP_OTHER", friendly_errors()["HTTP_OTHER"])

        h = hashlib.sha256()
        done = 0
        try:
            with open(tmp_path, "wb") as f:
                while True:
                    if cancel_event is not None and cancel_event.is_set():
                        raise UpdaterError("CANCELLED", friendly_errors()["CANCELLED"])
                    chunk = resp.read(256 * 1024)
                    if not chunk:
                        break
                    h.update(chunk)
                    f.write(chunk)
                    done += len(chunk)
                    if progress_cb:
                        progress_cb(done, expected_size)
        except UpdaterError:
            raise
        except OSError as e:
            if getattr(e, "errno", None) == 28:  # ENOSPC
                raise UpdaterError("DISK_FULL", friendly_errors()["DISK_FULL"])
            raise UpdaterError("PERMISSION", friendly_errors()["PERMISSION"])
        except Exception:
            raise UpdaterError("NETWORK", friendly_errors()["NETWORK"])
        finally:
            try:
                resp.close()
            except Exception:
                pass

        if done != expected_size:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise UpdaterError("SIZE_MISMATCH", friendly_errors()["SIZE_MISMATCH"])
        digest = h.hexdigest()
        if digest != expected_sha:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise UpdaterError("HASH_MISMATCH", friendly_errors()["HASH_MISMATCH"])

    def download_file(self, relpath: str, tmp_path: str,
                      expected_size: int, expected_sha: str,
                      progress_cb: Optional[Callable[[int, int], None]] = None,
                      cancel_event: Optional[threading.Event] = None) -> None:
        """Descarga un mod individual de la carpeta mods/ del repositorio."""
        url = (f"{self.base}/{CONFIG['mods_subfolder']}/"
               f"{urllib.parse.quote(relpath, safe='/')}")
        self._download_to(url, tmp_path, expected_size, expected_sha,
                          progress_cb, cancel_event, context=relpath)

    def download_archive(self, archive_name: str, tmp_path: str,
                         expected_size: int, expected_sha: str,
                         progress_cb: Optional[Callable[[int, int], None]] = None,
                         cancel_event: Optional[threading.Event] = None) -> None:
        """Descarga el pack completo (mods.zip) de la raíz del repositorio."""
        url = f"{self.base}/{urllib.parse.quote(archive_name)}"
        self._download_to(url, tmp_path, expected_size, expected_sha,
                          progress_cb, cancel_event, context=archive_name)


# ---------------------------------------------------------------------------
# 8. GESTOR DE ARCHIVOS  (seguridad de rutas, staging, backups, rollback)
# ---------------------------------------------------------------------------
def extract_verified_zip(zip_path: str, staging_dir: str,
                         manifest_files: Dict[str, Dict[str, Any]],
                         needed: Optional[set] = None,
                         tracker: Optional["ProgressTracker"] = None,
                         cancel_event: Optional[threading.Event] = None
                         ) -> Tuple[int, List[str]]:
    """
    Extrae del zip SOLO las entradas listadas en el manifiesto (y, si se
    indica, solo las necesarias), verificando tamaño y SHA-256 de cada archivo
    mientras se escribe. Devuelve (archivos_ok, errores).
    Cualquier entrada ajena, ruta peligrosa o archivo que no verifique se
    descarta: el zip nunca puede plantar ni corromper nada fuera de lo oficial.
    """
    ok = 0
    errors: List[str] = []
    with zipfile.ZipFile(zip_path) as z:
        jobs: List[Tuple[str, str, str, Dict[str, Any]]] = []
        for raw in z.namelist():
            rel = raw.replace("\\", "/")
            if rel.endswith("/"):
                continue                    # entrada de directorio
            if rel not in manifest_files:
                LOG.warning("entrada del zip ajena al manifiesto, se ignora: %s", rel)
                continue
            if needed is not None and rel not in needed:
                continue                    # ya está correcto en disco
            dst = safe_join(staging_dir, rel)
            if not dst:
                LOG.warning("entrada del zip insegura, se ignora: %s", rel)
                continue
            jobs.append((raw, rel, dst, manifest_files[rel]))
        total = sum(m["size"] for _, _, _, m in jobs)
        acc = 0
        for raw, rel, dst, meta in jobs:
            if cancel_event is not None and cancel_event.is_set():
                raise UpdaterError("CANCELLED", friendly_errors()["CANCELLED"])
            ensure_dir(os.path.dirname(dst))
            h = hashlib.sha256()
            size = 0
            try:
                with z.open(raw) as src, open(dst, "wb") as out:
                    while True:
                        chunk = src.read(256 * 1024)
                        if not chunk:
                            break
                        h.update(chunk)
                        out.write(chunk)
                        size += len(chunk)
                        acc += len(chunk)
                        if tracker is not None:
                            tracker.update(rel, acc, total)
            except Exception as e:
                LOG.error("no se pudo extraer %s: %s", rel, e)
                errors.append(rel)
                try:
                    os.remove(dst)
                except OSError:
                    pass
                continue
            if size != meta["size"] or h.hexdigest() != meta["sha256"]:
                LOG.error("verificación fallida al extraer %s", rel)
                errors.append(rel)
                try:
                    os.remove(dst)
                except OSError:
                    pass
            else:
                ok += 1
                if tracker is not None:
                    tracker.file_done(rel, size)
    return ok, errors


class FileOps:
    """Operaciones seguras sobre la carpeta de mods + sistema transaccional."""

    def __init__(self, mods_folder: str):
        self.mods = mods_folder
        self.staging = os.path.join(mods_folder, CONFIG["staging_dir_name"])
        self.journal_path = os.path.join(self.staging, "apply_journal.json")
        # El backup vive JUNTO a la carpeta de mods (carpeta oculta en el padre):
        # garantiza el MISMO volumen → movimientos atómicos y sin copias
        # cruzadas lentas, aunque .minecraft esté en otra unidad.
        self.backup_root = os.path.join(
            os.path.dirname(os.path.normpath(mods_folder)), ".exoverse_backup")

    # -- Preparación ------------------------------------------------------
    def clean_stale(self) -> bool:
        """Si una ejecución anterior se interrumpió, restaura desde el journal."""
        if not os.path.exists(self.staging):
            return False
        restored = False
        if os.path.exists(self.journal_path):
            try:
                with open(self.journal_path, "r", encoding="utf-8") as f:
                    journal = json.load(f)
                restored = self._rollback(journal)
                if restored:
                    # limpiar los run-dirs de backup del corte (ya restaurados)
                    # y subir borrando padres vacíos hasta el límite de backup_root
                    for entry in journal:
                        b = entry.get("backup")
                        if not b:
                            continue
                        run_dir = os.path.dirname(b)
                        shutil.rmtree(run_dir, ignore_errors=True)
                        parent = os.path.dirname(run_dir)
                        while (os.path.isdir(parent) and not os.listdir(parent)
                               and os.path.normcase(os.path.realpath(parent))
                               .startswith(os.path.normcase(os.path.realpath(self.backup_root)))):
                            try:
                                os.rmdir(parent)
                            except OSError:
                                break
                            parent = os.path.dirname(parent)
            except Exception as e:
                LOG.error("journal ilegible, no se puede restaurar: %s", e)
        shutil.rmtree(self.staging, ignore_errors=True)
        return restored

    def new_backup_run_dir(self) -> str:
        ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        d = os.path.join(self.backup_root, ts)
        ensure_dir(d)
        return d

    def prune_backups(self, keep: int = 0) -> None:
        """Borra generaciones de backup antiguas (por defecto conserva `keep`).
        También elimina run-dirs vacíos y el padre si queda vacío."""
        try:
            if not os.path.isdir(self.backup_root):
                return
            runs = sorted([d for d in os.listdir(self.backup_root)
                           if os.path.isdir(os.path.join(self.backup_root, d))])
            for old in runs[:-keep] if keep > 0 else runs:
                shutil.rmtree(os.path.join(self.backup_root, old), ignore_errors=True)
                LOG.info("backup antiguo eliminado: %s", old)
            # limpiar run-dirs vacíos (restos de operaciones sin cambios)
            for d in os.listdir(self.backup_root):
                p = os.path.join(self.backup_root, d)
                if os.path.isdir(p) and not os.listdir(p):
                    shutil.rmtree(p, ignore_errors=True)
            if os.path.isdir(self.backup_root) and not os.listdir(self.backup_root):
                os.rmdir(self.backup_root)
        except Exception as e:
            LOG.warning("no se pudieron limpiar backups: %s", e)

    # -- Aplicación con journal -------------------------------------------
    def apply(self, plan: "Plan", source: "RemoteSource") -> int:
        """
        Aplica el plan de forma transaccional:
          1. mueve los archivos que se van a reemplazar/eliminar a un backup delta;
          2. instala los nuevos (os.replace, atómico);
          3. escribe el manifiesto local;
        Si algo falla a mitad, restaura TODO desde el journal (rollback).
        Devuelve el número de archivos cambiados.
        """
        journal: List[Dict[str, Any]] = []
        self._backup_run: Optional[str] = None
        changed = 0

        def backup_existing(rel: str) -> Optional[str]:
            """Mueve el archivo local actual al backup; devuelve su ruta de backup.
            El run-dir de backup se crea de forma perezosa: si no hay nada que
            respaldar (instalación limpia), no se crea ningún directorio."""
            dst = safe_join(self.mods, rel)
            if not dst or not os.path.exists(dst):
                return None
            if self._backup_run is None:
                self._backup_run = self.new_backup_run_dir()
            bdst = safe_join(self._backup_run, rel)
            if not bdst:
                return None
            ensure_dir(os.path.dirname(bdst))
            try:
                shutil.move(dst, bdst)
            except PermissionError:
                raise UpdaterError("FILE_LOCKED", friendly_errors()["FILE_LOCKED"])
            except OSError as e:
                if getattr(e, "errno", None) == 28:
                    raise UpdaterError("DISK_FULL", friendly_errors()["DISK_FULL"])
                raise UpdaterError("PERMISSION", friendly_errors()["PERMISSION"])
            return bdst

        try:
            # Nota: clean_stale() ya se ejecutó antes de descargar (en update()).
            # Aquí NUNCA se limpia el staging: contiene los archivos verificados.
            ensure_dir(self.staging)

            install = plan.added + plan.updated

            # 1. Instalar / actualizar
            for fc in install:
                if not fc.ok_path:
                    continue
                src = safe_join(self.staging, fc.rel)
                dst = safe_join(self.mods, fc.rel)
                if not src or not dst or not os.path.exists(src):
                    raise UpdaterError("APPLY_FAILED", friendly_errors()["APPLY_FAILED"])
                ensure_dir(os.path.dirname(dst))
                backup_path = backup_existing(fc.rel)
                try:
                    os.replace(src, dst)
                except PermissionError:
                    raise UpdaterError("FILE_LOCKED", friendly_errors()["FILE_LOCKED"])
                except OSError as e:
                    if getattr(e, "errno", None) == 28:
                        raise UpdaterError("DISK_FULL", friendly_errors()["DISK_FULL"])
                    raise UpdaterError("PERMISSION", friendly_errors()["PERMISSION"])
                journal.append({"kind": "install", "rel": fc.rel,
                                "backup": backup_path})
                changed += 1
                # persiste el journal para poder restaurar tras un corte
                atomic_write_json(self.journal_path, journal)

            # 2. Eliminar solo archivos gestionados obsoletos
            for fc in plan.removed:
                dst = safe_join(self.mods, fc.rel)
                if not dst or not os.path.exists(dst):
                    continue
                backup_path = backup_existing(fc.rel)
                journal.append({"kind": "remove", "rel": fc.rel,
                                "backup": backup_path})
                changed += 1
                atomic_write_json(self.journal_path, journal)

            # 3. Manifiesto local (escritura atómica). Orden crítico:
            #    1º borrar journal (marca de éxito) → 2º manifiesto → 3º staging,
            #    para que un corte de luz en este punto nunca deje un estado raro.
            if os.path.exists(self.journal_path):
                os.remove(self.journal_path)
            if plan.remote_manifest is not None:
                ManifestManager.save_local(self.mods, plan.remote_manifest)
            shutil.rmtree(self.staging, ignore_errors=True)
            return changed

        except UpdaterError:
            LOG.exception("error aplicando cambios; ejecutando rollback")
            self._rollback_and_cleanup(journal)
            raise
        except Exception as e:
            LOG.exception("error aplicando cambios; ejecutando rollback")
            self._rollback_and_cleanup(journal)
            raise UpdaterError("APPLY_FAILED", friendly_errors()["APPLY_FAILED"]) from e

    def _rollback_and_cleanup(self, journal: List[Dict[str, Any]]) -> None:
        """Rollback y limpieza completa: journal y staging NO deben sobrevivir
        a un rollback ya ejecutado (evita re-restauraciones en el próximo arranque).
        Si el rollback es 100% exitoso, también se elimina el backup de la
        operación fallida (las copias huérfanas no deben acumularse)."""
        ok = False
        try:
            ok = self._rollback(journal)
        except Exception:
            LOG.exception("rollback fallido")
        finally:
            if os.path.exists(self.journal_path):
                try:
                    os.remove(self.journal_path)
                except OSError:
                    pass
            shutil.rmtree(self.staging, ignore_errors=True)
            if ok and self._backup_run and os.path.isdir(self._backup_run):
                shutil.rmtree(self._backup_run, ignore_errors=True)
            # el padre puede quedar vacío → limpiarlo también (best-effort)
            parent_bk = os.path.dirname(self._backup_run) if self._backup_run else None
            if ok and parent_bk and os.path.isdir(parent_bk):
                try:
                    os.rmdir(parent_bk)
                except OSError:
                    pass

    def _rollback(self, journal: List[Dict[str, Any]]) -> bool:
        """Restaura el estado anterior a partir del journal (en orden inverso).
        Devuelve True si TODAS las entradas se restauraron correctamente."""
        all_ok = True
        for entry in reversed(journal):
            rel = entry.get("rel", "")
            dst = safe_join(self.mods, rel)
            if not dst:
                all_ok = False
                continue
            backup = entry.get("backup")
            try:
                if backup and os.path.exists(backup):
                    ensure_dir(os.path.dirname(dst))
                    shutil.move(backup, dst)
                elif entry.get("kind") == "install":
                    # archivo nuevo instalado y sin backup → se elimina
                    if os.path.exists(dst):
                        os.remove(dst)
            except Exception as e:
                LOG.error("rollback: no se pudo restaurar %s: %s", rel, e)
                all_ok = False
        return all_ok


# ---------------------------------------------------------------------------
# 9. DETECTOR DE MINECRAFT  (carpeta de mods + procesos en ejecución)
# ---------------------------------------------------------------------------
class MinecraftDetector:
    GAME_PROCS = {"javaw.exe", "java.exe"}
    LAUNCHER_PROCS = {"minecraftlauncher.exe", "curseforge.exe", "prismlauncher.exe",
                      "multimc.exe", "atlauncher.exe", "gdlauncher.exe", "ftbapp.exe",
                      "tlauncher.exe", "lunarclient.exe", "badlionclient.exe", "pclauncher.exe"}

    @staticmethod
    def default_mods_folder() -> Optional[str]:
        """Localiza la carpeta de mods en los launchers más comunes (Windows).

        Orden de preferencia:
          1. Cualquier carpeta que ya tenga el manifiesto de ExoVerse
             (.exoverse_manifest.json) — es donde el jugador ya sincronizó.
          2. La que contenga más .jar (probablemente la del pack).
          3. La primera que exista (aunque esté vacía).
          4. %APPDATA%\\.minecraft\\mods (se crea si .minecraft existe).
        """
        appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
        candidates: List[str] = [
            os.path.join(appdata, ".minecraft", "mods"),
            os.path.join(appdata, "minecraft", "mods"),   # launcher antiguo
        ]
        # Launchers con instancias propias (SKLauncher, Prism, MultiMC, CurseForge)
        for pattern in (
            os.path.join(appdata, ".sklauncher", "instances", "*", "mods"),
            os.path.join(appdata, ".sklauncher", "instances", "*", ".minecraft", "mods"),
            os.path.join(appdata, "PrismLauncher", "instances", "*", ".minecraft", "mods"),
            os.path.join(appdata, "MultiMC", "instances", "*", ".minecraft", "mods"),
        ):
            candidates.extend(sorted(glob.glob(pattern)))
        cf = os.environ.get("CURSEFORGE") or \
            os.path.join(appdata, "com.overwolf.curseforge")
        candidates.append(os.path.join(cf, "Minecraft", "Instances", "*", "mods"))

        seen: set = set()
        first_existing: Optional[str] = None
        best: Optional[Tuple[str, int]] = None
        for c in candidates:
            c = os.path.normpath(c)
            if c in seen:
                continue
            seen.add(c)
            if not os.path.isdir(c):
                continue
            if first_existing is None:
                first_existing = c
            # 1. ¿Esta carpeta ya está gestionada por ExoVerse?
            if os.path.exists(os.path.join(c, CONFIG["local_manifest_name"])):
                LOG.info("carpeta de mods candidata con manifiesto ExoVerse: %s", c)
                return c
            # 2. ¿Cuántos mods tiene?
            try:
                jars = sum(1 for f in os.listdir(c)
                           if f.lower().endswith(".jar") and
                           os.path.isfile(os.path.join(c, f)))
            except OSError:
                jars = 0
            if best is None or jars > best[1]:
                best = (c, jars)
        # 3. La que más mods tenga (si tiene alguno)
        if best is not None and best[1] > 0:
            LOG.info("carpeta de mods candidata (más mods): %s", best[0])
            return best[0]
        # 4. La primera que exista aunque esté vacía
        if first_existing is not None:
            return first_existing
        # 5. Si existe .minecraft → su carpeta mods (se creará al usarla)
        mc = os.path.join(appdata, ".minecraft")
        if os.path.isdir(mc):
            return os.path.join(mc, "mods")
        return None

    @staticmethod
    def _process_names() -> List[str]:
        """Nombres de procesos en ejecución (solo Windows, vía ctypes, sin subprocesos)."""
        if os.name != "nt":
            return []
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

            class PROCESSENTRY32W(ctypes.Structure):
                _fields_ = [("dwSize", ctypes.c_ulong), ("cntUsage", ctypes.c_ulong),
                            ("th32ProcessID", ctypes.c_ulong),
                            ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                            ("th32ModuleID", ctypes.c_ulong), ("cntThreads", ctypes.c_ulong),
                            ("th32ParentProcessID", ctypes.c_ulong),
                            ("pcPriClassBase", ctypes.c_long), ("dwFlags", ctypes.c_ulong),
                            ("szExeFile", ctypes.c_wchar * 260)]

            TH32CS_SNAPPROCESS = 0x00000002
            snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
            if not snapshot or snapshot == -1:
                return []
            names: List[str] = []
            try:
                entry = PROCESSENTRY32W()
                entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
                ok = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
                while ok:
                    names.append(entry.szExeFile.lower())
                    ok = kernel32.Process32NextW(snapshot, ctypes.byref(entry))
            finally:
                kernel32.CloseHandle(snapshot)
            return names
        except Exception as e:
            LOG.warning("no se pudo enumerar procesos: %s", e)
            return []

    @classmethod
    def running_status(cls) -> Tuple[bool, bool]:
        """Devuelve (minecraft_abierto, launcher_abierto)."""
        names = set(cls._process_names())
        game = bool(names & cls.GAME_PROCS)
        launcher = bool(names & cls.LAUNCHER_PROCS)
        if game or launcher:
            LOG.info("procesos detectados: %s", ", ".join(sorted(names & (cls.GAME_PROCS | cls.LAUNCHER_PROCS))))
        return game, launcher


# ---------------------------------------------------------------------------
# 10. PLAN DE CAMBIOS
# ---------------------------------------------------------------------------
@dataclass
class FileChange:
    rel: str
    action: str            # 'added' | 'updated' | 'removed' | 'ok'
    size: int              # tamaño oficial (remoto)
    display_name: str = "" # nombre bonito (del jar), opcional
    ok_path: str = ""      # ruta del archivo ya descargado (fase de aplicar)

    @property
    def label(self) -> str:
        return self.display_name or os.path.basename(self.rel)


@dataclass
class Plan:
    remote_manifest: Optional[Dict[str, Any]]
    added: List[FileChange] = field(default_factory=list)
    updated: List[FileChange] = field(default_factory=list)
    removed: List[FileChange] = field(default_factory=list)
    ok: List[FileChange] = field(default_factory=list)
    is_first_install: bool = False
    total_bytes: int = 0        # bytes que se descargarán (modo zip: tamaño del zip)
    extracted_bytes: int = 0    # bytes que se escribirán en disco (suma de los mods)

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.updated or self.removed)

    @property
    def counts(self) -> Tuple[int, int, int]:
        return len(self.added), len(self.updated), len(self.removed)


class PlanBuilder:
    """Construye el plan comparando el manifiesto remoto con el local y el disco.

    Política de verificación (compromiso velocidad/fiabilidad):
      • Comparación de METADATOS (hash+size del manifiesto): gratis.
      • Comparación de TAMAÑO real en disco: gratis (stat).
      • SHA-256 del disco: solo en modo REPARAR o al verificar descargas.
    Así, una comprobación normal no calcula hashes de 2 GB en cada arranque,
    pero una descarga siempre queda verificada antes de aplicarse.
    """

    @staticmethod
    def build(remote: Dict[str, Any], local: Optional[Dict[str, Any]],
              mods_folder: str, deep: bool = False) -> Plan:
        plan = Plan(remote_manifest=remote, is_first_install=local is None)
        local_files: Dict[str, Dict[str, Any]] = (local or {}).get("files", {})
        unsafe_logged = False

        for rel in sorted(remote["files"].keys()):
            meta = remote["files"][rel]
            # Seguridad: la ruta debe quedarse dentro de la carpeta de mods
            dest = safe_join(mods_folder, rel)
            if not dest:
                if not unsafe_logged:
                    LOG.warning("ruta insegura ignorada en el manifiesto: %r", rel)
                    unsafe_logged = True
                continue
            disk_size = os.path.getsize(dest) if os.path.isfile(dest) else None
            lok = local_files.get(rel)

            if lok is None:
                # No gestionado todavía: si el archivo ya está con el tamaño
                # oficial, se adopta (evita re-descargar tras perder el manifiesto).
                if disk_size == meta["size"]:
                    plan.ok.append(FileChange(rel, "ok", meta["size"]))
                else:
                    plan.added.append(FileChange(rel, "added", meta["size"]))
                continue

            if lok == meta:  # mismo hash y tamaño registrados
                if disk_size == meta["size"]:
                    plan.ok.append(FileChange(rel, "ok", meta["size"]))
                else:
                    # archivo dañado/incompleto → descargar de nuevo
                    plan.updated.append(FileChange(rel, "updated", meta["size"]))
                continue

            # El registro local no coincide con el remoto → actualización oficial
            if deep and disk_size == meta["size"]:
                # Reparar: verificar hash real antes de decidir
                try:
                    if sha256_file(dest) == meta["sha256"]:
                        plan.ok.append(FileChange(rel, "ok", meta["size"]))
                        continue
                except OSError:
                    pass
            plan.updated.append(FileChange(rel, "updated", meta["size"]))

        # Eliminados: archivos gestionados que ya no están en el pack oficial
        for rel in sorted(local_files.keys()):
            if rel not in remote["files"]:
                plan.removed.append(FileChange(rel, "removed",
                                               local_files[rel].get("size", 0)))
        # Bytes: en modo "zip" se descarga el archivo completo (no por archivo)
        files_bytes = sum(fc.size for fc in plan.added + plan.updated)
        plan.extracted_bytes = files_bytes
        plan.total_bytes = (int(remote.get("archive_size", 0))
                            if remote.get("dist") == "zip" else files_bytes)
        return plan


# ---------------------------------------------------------------------------
# 11. SEGUIMIENTO DE PROGRESO  (descargas en paralelo, velocidad, bytes)
# ---------------------------------------------------------------------------
class ProgressTracker:
    """Agrega progreso de varios hilos y emite eventos con throttle (≤10/s)."""

    def __init__(self, emit: Callable[[Dict[str, Any]], None]):
        self.emit = emit
        self.lock = threading.Lock()
        self.done_bytes = 0
        self.total_bytes = 0
        self.done_files = 0
        self.total_files = 0
        self.current_name = ""
        self.current_done = 0
        self.current_total = 0
        self.phase = "download"
        self._samples: List[Tuple[float, int]] = []
        self._last_emit = 0.0

    def begin(self, total_bytes: int, total_files: int, phase: str = "download") -> None:
        with self.lock:
            self.total_bytes = total_bytes
            self.total_files = total_files
            self.done_bytes = 0
            self.done_files = 0
            self.phase = phase
            self._samples = [(time.time(), 0)]
            self._last_emit = 0.0
        self._emit_now()

    def file_done(self, name: str, size: int) -> None:
        with self.lock:
            self.done_files += 1
        self._emit_now()

    def update(self, name: str, done: int, total: int) -> None:
        with self.lock:
            self.current_name = name
            self.current_done = done
            self.current_total = total
            now = time.time()
            delta = done - self.done_bytes
            self.done_bytes = done
            self._samples.append((now, done))
            # ventana deslizante de ~3 s
            cutoff = now - 3.0
            self._samples = [(t, b) for t, b in self._samples if t >= cutoff]
            speed = 0.0
            if len(self._samples) >= 2:
                t0, b0 = self._samples[0]
                dt = now - t0
                if dt > 0.2:
                    speed = (done - b0) / dt
            self._speed = speed
        self._emit_now()

    def _emit_now(self) -> None:
        now = time.time()
        if now - self._last_emit < 0.1:
            return
        self._last_emit = now
        with self.lock:
            ev = {
                "t": "progress",
                "phase": self.phase,
                "done": self.done_bytes,
                "total": self.total_bytes,
                "done_files": self.done_files,
                "total_files": self.total_files,
                "speed": getattr(self, "_speed", 0.0),
                "current_name": self.current_name,
                "current_done": self.current_done,
                "current_total": self.current_total,
            }
        self.emit(ev)


# ---------------------------------------------------------------------------
# 12. MOTOR DEL UPDATER  (lógica pura, sin GUI; se comunica por eventos)
# ---------------------------------------------------------------------------
class UpdaterEngine:
    """Orquesta: carpeta de mods → manifiesto → plan → descarga → aplicación.

    Eventos emitidos (dict) hacia la UI / consola:
      {'t':'status','kind':'info|ok|warn|err','text'}   estado principal
      {'t':'versions','local':str|None,'remote':str|None}
      {'t':'plan','plan':…}                               cambios detectados
      {'t':'progress', …}                                 avance de descarga/aplicación
      {'t':'minecraft_running','game':bool,'launcher':bool}
      {'t':'file_done','name':…,'size':…}
      {'t':'done','summary':str,'count':int,'version':str}
      {'t':'error','code':str,'message':str}
    """

    def __init__(self, emit: Callable[[Dict[str, Any]], None]):
        self.emit = emit
        self.cancel_event = threading.Event()
        self.force = False                      # 'actualizar de todos modos'
        self.mods_folder: Optional[str] = None
        self.user_config = UserConfig()
        self.source = RemoteSource()
        self.plan: Optional[Plan] = None
        self._current_op = ""
        self._folder_changed = False

    # -- Carpeta de mods ---------------------------------------------------
    def resolve_mods_folder(self, manual: Optional[str] = None) -> str:
        """Localiza la carpeta de mods; valida escritura; recuerda la elección."""
        chosen: Optional[str] = None
        if manual:
            chosen = os.path.expandvars(os.path.expanduser(manual.strip()))
        else:
            cfg = self.user_config.get("mods_folder")
            if cfg and os.path.isdir(cfg):
                chosen = cfg
            else:
                chosen = MinecraftDetector.default_mods_folder()

        if not chosen:
            raise UpdaterError("FOLDER_NOT_FOUND", friendly_errors()["FOLDER_NOT_FOUND"])

        # Si el usuario eligió la raíz de .minecraft, apuntar a su subcarpeta mods
        if os.path.basename(os.path.normpath(chosen)).lower() in (".minecraft", "minecraft"):
            chosen = os.path.join(chosen, "mods")

        # ¿Se permite crear la carpeta si no existe?
        #  - Sí: la eligió el jugador explícitamente (manual).
        #  - Sí: es la carpeta estándar %APPDATA%\.minecraft\mods (padre existe).
        #  - No: cualquier otra ruta automática inexistente (evita crear carpetas raras).
        if not os.path.isdir(chosen):
            can_create = manual is not None
            if not can_create:
                parent = os.path.dirname(os.path.normpath(chosen))
                can_create = (os.path.basename(os.path.normpath(chosen)).lower() == "mods"
                              and os.path.isdir(parent))
            if not can_create:
                raise UpdaterError("FOLDER_NOT_FOUND", friendly_errors()["FOLDER_NOT_FOUND"])

        # Probar escritura (crea la carpeta si hace falta + archivo de prueba)
        try:
            ensure_dir(chosen)
            probe = os.path.join(chosen, ".exoverse_write_test")
            with open(probe, "wb") as f:
                f.write(b"ok")
            os.remove(probe)
        except OSError:
            raise UpdaterError("FOLDER_NOT_WRITABLE", friendly_errors()["FOLDER_NOT_WRITABLE"])

        if self.mods_folder != chosen:
            self._folder_changed = True
        self.mods_folder = chosen
        if self.user_config.get("mods_folder") != chosen:
            self.user_config.set("mods_folder", chosen)
        LOG.info("carpeta de mods: %s", chosen)

        # Recuperación de una actualización interrumpida (journal + staging)
        try:
            if FileOps(chosen).clean_stale():
                LOG.info("se restauró una actualización interrumpida")
        except Exception as e:
            LOG.warning("no se pudo limpiar restos de staging: %s", e)
        return chosen

    # -- Comprobación ------------------------------------------------------
    def check(self, deep: bool = False, mods_folder: Optional[str] = None) -> Plan:
        self._begin_op("check")
        try:
            if mods_folder:
                self.resolve_mods_folder(mods_folder)
            if not self.mods_folder:
                self.resolve_mods_folder()

            self.emit({"t": "status", "kind": "info",
                       "text": "Conectando con GitHub…"})
            LOG.info("comprobando actualizaciones (deep=%s)", deep)

            manifest: Optional[Dict[str, Any]] = None
            etag: Optional[str] = None
            unchanged = False
            try:
                manifest, etag, unchanged = self.source.fetch_manifest(
                    self.user_config.get("manifest_etag"))
                if (manifest is None and not unchanged and self.source.use_api_fallback):
                    # raw falló con 404/403 y no es un 304 → probar API REST
                    manifest, etag, unchanged = self.source.fetch_manifest_fallback_api(
                        self.user_config.get("manifest_etag"))
            except UpdaterError as e:
                # ¿Hay un fallback disponible (API) sin usar todavía?
                if (self.source.use_api_fallback and e.code in ("HTTP_404_MANIFEST",
                                                                 "NETWORK", "OFFLINE", "HTTP_OTHER")):
                    try:
                        manifest, etag, unchanged = self.source.fetch_manifest_fallback_api(
                            self.user_config.get("manifest_etag"))
                    except UpdaterError as e2:
                        raise e2
                else:
                    raise

            if unchanged:
                # El servidor dice que el manifiesto no ha cambiado.
                local, corrupt = ManifestManager.load_local(self.mods_folder)
                if local is not None:
                    self.plan = PlanBuilder.build(local, local, self.mods_folder, deep=False)
                    self.plan.remote_manifest = local
                    self._emit_versions(local["version"], local["version"])
                    self._emit_ok_up_to_date(local["version"])
                    self._emit_plan_if_changes(self.plan)
                    return self.plan
                # Sin manifiesto local: necesitamos el contenido → pedir sin ETag
                manifest, etag, unchanged = self.source.fetch_manifest(None)

            if manifest is None:
                raise UpdaterError("MANIFEST_INVALID", friendly_errors()["MANIFEST_INVALID"])

            if etag:
                self.user_config.set("manifest_etag", etag)
            self.user_config.set("last_known_version", manifest["version"])

            LOG.info("manifiesto remoto: versión %s, %d archivos, %s, modo=%s",
                     manifest["version"], len(manifest["files"]),
                     hsize(manifest["total_size"]), manifest.get("dist", "folder"))

            self.emit({"t": "status", "kind": "info",
                       "text": "Comprobando actualizaciones…"})

            local, local_corrupt = ManifestManager.load_local(self.mods_folder)
            if local_corrupt:
                self.emit({"t": "status", "kind": "warn",
                           "text": friendly_errors()["MANIFEST_LOCAL_CORRUPT"]})
            local_version = (local or {}).get("version")
            self._emit_versions(local_version, manifest["version"])

            self.plan = PlanBuilder.build(manifest, local, self.mods_folder, deep=deep)

            if not self.plan.has_changes:
                self._emit_ok_up_to_date(manifest["version"])
                self._emit_plan_if_changes(self.plan)
                return self.plan

            # Cambios detectados → resumen
            a, u, r = self.plan.counts
            LOG.info("cambios: +%d actualizar=%d -%d (%.1f MB)",
                     a, u, r, self.plan.total_bytes / 1048576.0)
            self._emit_plan_if_changes(self.plan)
            return self.plan

        finally:
            self._end_op()

    # -- Actualización -----------------------------------------------------
    def update(self, plan: Optional[Plan] = None) -> int:
        """Recomprueba el estado y aplica los cambios si los hay."""
        self._begin_op("update")
        self.cancel_event.clear()
        try:
            if not self.mods_folder:
                self.resolve_mods_folder()

            # 0. Minecraft abierto → no tocar la carpeta de mods
            if not self.force:
                self.emit({"t": "status", "kind": "info",
                           "text": "Comprobando Minecraft…"})
                game, launcher = MinecraftDetector.running_status()
                if game:
                    self.emit({"t": "minecraft_running", "game": True, "launcher": launcher})
                    LOG.warning("Minecraft en ejecución; se detiene la actualización")
                    self._end_op()
                    return -1
                if launcher:
                    self.emit({"t": "status", "kind": "warn",
                               "text": "El launcher de Minecraft está abierto. "
                                       "Asegúrate de que el juego esté cerrado."})

            # 1. Manifiesto fresco (el servidor pudo cambiar desde la última comprobación)
            manifest, etag, unchanged = self.source.fetch_manifest(
                self.user_config.get("manifest_etag"))
            if manifest is None and unchanged:
                manifest, etag, unchanged = self.source.fetch_manifest(None)
            if manifest is None:
                raise UpdaterError("MANIFEST_INVALID", friendly_errors()["MANIFEST_INVALID"])
            if etag:
                self.user_config.set("manifest_etag", etag)

            local, _ = ManifestManager.load_local(self.mods_folder)
            self.plan = PlanBuilder.build(manifest, local, self.mods_folder, deep=False)

            if not self.plan.has_changes:
                self._emit_ok_up_to_date(manifest["version"])
                return 0

            # 2. Espacio en disco (zip: se necesita el zip + los mods extraídos)
            dist = (self.plan.remote_manifest or {}).get("dist", "folder")
            need_bytes = self.plan.total_bytes + (
                self.plan.extracted_bytes if dist == "zip" else 0)
            need = int(need_bytes * CONFIG["disk_margin_factor"]) \
                + CONFIG["disk_margin_bytes"]
            try:
                free = shutil.disk_usage(self.mods_folder).free
            except OSError:
                free = 0
            if free < need:
                raise UpdaterError("DISK_FULL",
                                   friendly_errors()["DISK_FULL"] +
                                   f"\nSe necesitan al menos {hsize(need)} libres.")

            # 3. Preparar archivos en staging (descarga verificada)
            self.emit({"t": "status", "kind": "info", "text": "Descargando archivos…"})
            install = self.plan.added + self.plan.updated
            tracker = ProgressTracker(self.emit)
            fileops = FileOps(self.mods_folder)
            fileops.clean_stale()
            ensure_dir(fileops.staging)
            manifest = self.plan.remote_manifest or {}

            try:
                if dist == "zip":
                    # ── Modo mods.zip: 1 descarga + extracción verificada ──
                    archive_name = manifest["archive"]
                    archive_path = os.path.join(fileops.staging, f"__{archive_name}")
                    tracker.begin(int(manifest["archive_size"]), 1, phase="download")
                    self.source.download_archive(
                        archive_name, archive_path,
                        int(manifest["archive_size"]), manifest["archive_sha256"],
                        progress_cb=lambda done, total: tracker.update(
                            archive_name, done, total),
                        cancel_event=self.cancel_event)
                    tracker.file_done(archive_name, int(manifest["archive_size"]))
                    self.emit({"t": "status", "kind": "info",
                               "text": "Descomprimiendo y verificando archivos…"})
                    needed = {fc.rel for fc in install}
                    x_total = sum(manifest["files"][rel]["size"]
                                  for rel in manifest["files"] if rel in needed)
                    tracker.begin(x_total, len(install), phase="extract")
                    ok_n, errs = extract_verified_zip(
                        archive_path, fileops.staging, manifest["files"],
                        needed=needed, tracker=tracker,
                        cancel_event=self.cancel_event)
                    if errs:
                        LOG.error("errores extrayendo el zip: %s", errs[:8])
                        raise UpdaterError("ARCHIVE_INVALID",
                                           friendly_errors()["ARCHIVE_INVALID"])
                    LOG.info("zip extraído y verificado: %d archivos", ok_n)
                    # ¿El zip carece de algún archivo que el plan necesita?
                    missing = []
                    for fc in install:
                        p = safe_join(fileops.staging, fc.rel)
                        if not p or not os.path.exists(p):
                            missing.append(fc.rel)
                    if missing:
                        LOG.error("archivos ausentes en el zip: %s", missing[:8])
                        raise UpdaterError("ARCHIVE_INCOMPLETE",
                                           friendly_errors()["ARCHIVE_INCOMPLETE"])
                    for fc in install:
                        fc.ok_path = safe_join(fileops.staging, fc.rel)
                else:
                    # ── Modo carpeta: descargas paralelas por archivo ──
                    tracker.begin(self.plan.total_bytes, len(install), phase="download")
                    errors: List[UpdaterError] = []
                    self.cancel_event.clear()

                    def work(fc: FileChange) -> Tuple[str, str, str]:
                        rel = fc.rel
                        src = safe_join(fileops.staging, rel)
                        if not src:
                            raise UpdaterError("UNSAFE_PATH",
                                               friendly_errors()["UNSAFE_PATH"])
                        ensure_dir(os.path.dirname(src))
                        self.source.download_file(
                            rel, src, fc.size, manifest["files"][rel]["sha256"],
                            progress_cb=lambda done, total: tracker.update(
                                rel, done, total),
                            cancel_event=self.cancel_event)
                        name = guess_mod_display_name(src) or os.path.basename(rel)
                        return rel, src, name

                    with ThreadPoolExecutor(
                            max_workers=CONFIG["max_parallel_downloads"]) as ex:
                        futures = {ex.submit(work, fc): fc for fc in install}
                        for fut in as_completed(futures):
                            fc = futures[fut]
                            try:
                                rel, src, name = fut.result()
                                fc.ok_path = src
                                fc.display_name = name
                                tracker.file_done(name or rel, fc.size)
                                self.emit({"t": "file_done", "name": name or rel,
                                           "size": fc.size})
                            except UpdaterError as e:
                                errors.append(e)
                                self.cancel_event.set()   # detener el resto
                            except Exception:
                                LOG.exception("error inesperado descargando %s", fc.rel)
                                errors.append(UpdaterError(
                                    "UNKNOWN", friendly_errors()["UNKNOWN"]))
                    if errors:
                        e0 = errors[0]
                        # Ayuda concreta si el repo no coincide con el modo declarado
                        if e0.code == "HTTP_404_FILE":
                            if dist == "zip":
                                e0.message += ("\n\nEl pack está configurado en modo «zip»: "
                                               "comprueba que el archivo mods.zip está subido "
                                               "a la raíz del repositorio.")
                            else:
                                e0.message += ("\n\nEl pack está configurado en modo «carpeta»: "
                                               "comprueba que la carpeta mods/ con los .jar "
                                               "está subida al repositorio.")
                        raise e0
            except UpdaterError:
                # Sin cambios aplicados todavía: limpiar staging y propagar
                shutil.rmtree(fileops.staging, ignore_errors=True)
                raise

            # 4. Aplicar transaccionalmente
            self.emit({"t": "status", "kind": "info", "text": "Aplicando cambios…"})
            tracker.begin(1, 1, phase="apply")
            changed = fileops.apply(self.plan, self.source)

            # 5. Limpieza de backups antiguos (solo tras éxito)
            fileops.prune_backups(CONFIG["backup_keep_generations"])

            a, u, r = self.plan.counts
            summary = (f"Mods actualizados correctamente.\n"
                       f"  + {a} añadidos · ↻ {u} actualizados · − {r} eliminados")
            LOG.info("actualización completada: %s", summary.replace("\n", " "))
            self.emit({"t": "done", "summary": summary, "count": changed,
                       "version": manifest["version"]})
            self.user_config.set("last_known_version", manifest["version"])
            return changed

        finally:
            self._end_op()

    # -- Reparación --------------------------------------------------------
    def repair(self) -> int:
        """Comprueba TODOS los archivos (hash real) y re-descarga lo dañado."""
        self._begin_op("repair")
        self.cancel_event.clear()
        try:
            self.emit({"t": "status", "kind": "info",
                       "text": "Verificando archivos (reparación)…"})
            plan = self.check(deep=True)
            if plan.has_changes:
                return self.update(plan)
            self.emit({"t": "status", "kind": "ok",
                       "text": "✓ Reparación completada. Todos los archivos están correctos."})
            return 0
        finally:
            self._end_op()

    # -- Cancelación -------------------------------------------------------
    def cancel(self) -> None:
        self.cancel_event.set()
        LOG.info("cancelación solicitada por el usuario")

    # -- Internos ----------------------------------------------------------
    def _begin_op(self, op: str) -> None:
        self._current_op = op
        self.cancel_event.clear()
        LOG.info("operación iniciada: %s", op)

    def _end_op(self) -> None:
        LOG.info("operación finalizada: %s", self._current_op)
        self._current_op = ""

    def _emit_versions(self, local: Optional[str], remote: Optional[str]) -> None:
        self.emit({"t": "versions", "local": local, "remote": remote})

    def _emit_ok_up_to_date(self, version: str) -> None:
        LOG.info("instalación actualizada (versión %s)", version)
        self.emit({"t": "status", "kind": "ok",
                   "text": "✓ Tu instalación está actualizada"})
        self.emit({"t": "plan", "plan": self._plan_to_dict(None)})

    def _emit_plan_if_changes(self, plan: Plan) -> None:
        self.emit({"t": "plan", "plan": self._plan_to_dict(plan)})

    def _plan_to_dict(self, plan: Optional[Plan]) -> Optional[Dict[str, Any]]:
        if plan is None:
            return None
        def ser(items: List[FileChange]) -> List[Dict[str, Any]]:
            return [{"rel": fc.rel, "name": os.path.basename(fc.rel),
                     "display": fc.label, "size": fc.size} for fc in items]
        return {
            "added": ser(plan.added),
            "updated": ser(plan.updated),
            "removed": ser(plan.removed),
            "total_bytes": plan.total_bytes,
            "first_install": plan.is_first_install,
            "has_changes": plan.has_changes,
        }


# ---------------------------------------------------------------------------
# 13. NOMBRE BONITO DEL MOD  (lee META-INF/mods.toml o fabric.mod.json del jar)
# ---------------------------------------------------------------------------
def guess_mod_display_name(jar_path: str) -> Optional[str]:
    try:
        with zipfile.ZipFile(jar_path) as z:
            names = z.namelist()
            if "META-INF/mods.toml" in names:
                data = z.read("META-INF/mods.toml").decode("utf-8", "replace")
                m = re.search(r'^\s*displayName\s*=\s*"([^"]+)"', data, re.M)
                if m:
                    return m.group(1).strip()[:60]
            if "fabric.mod.json" in names:
                try:
                    d = json.loads(z.read("fabric.mod.json").decode("utf-8", "replace"))
                    if isinstance(d, dict) and isinstance(d.get("name"), str) and d["name"]:
                        return d["name"][:60]
                except Exception:
                    pass
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# 14. INTERFAZ GRÁFICA  (tkinter, tema oscuro ExoVerse)
#     La GUI NUNCA hace red ni disco: el motor corre en un hilo y envía
#     eventos a una cola que la GUI drena con after().
# ---------------------------------------------------------------------------
import tkinter as tk
from tkinter import filedialog, messagebox


class ExoVerseApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(CONFIG["app_name"])
        self.root.configure(bg=THEME["bg"])
        self.root.minsize(620, 760)
        self.root.geometry("640x800")
        self._center_window()
        try:
            img = tk.PhotoImage(data=ICON_B64)
            self.root.iconphoto(True, img)
        except Exception:
            pass

        self.ui_queue: "queue.Queue[Dict[str, Any]]" = queue.Queue()
        self.busy = False
        self._ticker_scheduled = False
        self.engine = UpdaterEngine(emit=self._on_engine_event)
        self.plan: Optional[Dict[str, Any]] = None
        self._mc_blocked = False

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(200, self._startup)

    # ── Ventana ─────────────────────────────────────────────────────────
    def _center_window(self) -> None:
        self.root.update_idletasks()
        w, h = 640, 800
        x = max(0, (self.root.winfo_screenwidth() - w) // 2)
        y = max(0, (self.root.winfo_screenheight() - h) // 2 - 20)
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    # ── Construcción de widgets ─────────────────────────────────────────
    def _build_ui(self) -> None:
        fonts = {"title": ("Segoe UI", 26, "bold"), "sub": ("Segoe UI", 9),
                 "body": ("Segoe UI", 10), "small": ("Segoe UI", 9),
                 "big": ("Segoe UI", 12, "bold"), "mono": ("Consolas", 9)}

        # ── Cabecera con degradado ─────────────────────────────────────
        self.header = tk.Canvas(self.root, height=118, highlightthickness=0, bd=0)
        self.header.pack(fill="x")
        self.header.bind("<Configure>", self._draw_header)

        # ── Cuerpo ─────────────────────────────────────────────────────
        body = tk.Frame(self.root, bg=THEME["bg"])
        body.pack(fill="both", expand=True, padx=18, pady=(12, 6))

        # Tarjeta de estado
        self.card_status = self._card(body)
        self.card_status.pack(fill="x")

        self.status_label = tk.Label(self.card_status, text="Iniciando…",
                                     font=fonts["big"], bg=THEME["card"],
                                     fg=THEME["text"], anchor="w", justify="left",
                                     wraplength=560)
        self.status_label.pack(fill="x", padx=18, pady=(14, 4))

        self.sub_label = tk.Label(self.card_status, text="", font=fonts["small"],
                                  bg=THEME["card"], fg=THEME["muted"],
                                  anchor="w", justify="left", wraplength=560)
        self.sub_label.pack(fill="x", padx=18, pady=(0, 2))

        versions_row = tk.Frame(self.card_status, bg=THEME["card"])
        versions_row.pack(fill="x", padx=18, pady=(6, 4))
        self.v_local = tk.Label(versions_row, text="Instalada: —",
                                font=fonts["body"], bg=THEME["card"], fg=THEME["muted"])
        self.v_local.pack(side="left")
        self.v_remote = tk.Label(versions_row, text="Última: —",
                                 font=fonts["body"], bg=THEME["card"], fg=THEME["muted"])
        self.v_remote.pack(side="right")

        # Lista de cambios (oculta si no hay)
        self.changes_frame = tk.Frame(self.card_status, bg=THEME["card_border"])
        self.changes_text = tk.Text(self.changes_frame, height=9, wrap="word",
                                    font=fonts["body"], bg="#101830", fg=THEME["text"],
                                    bd=0, padx=12, pady=10, state="disabled",
                                    highlightthickness=0, cursor="arrow",
                                    selectbackground=THEME["accent"])
        self.changes_text.pack(fill="both", expand=True)
        for tag, color in (("add", THEME["ok"]), ("upd", THEME["info"]),
                           ("del", THEME["err"]), ("head", THEME["muted"]),
                           ("hdr", THEME["text"])):
            self.changes_text.tag_configure(tag, foreground=color)
        self.changes_text.tag_configure("hdr", font=("Segoe UI", 11, "bold"))
        self.changes_text.tag_configure("head", font=("Segoe UI", 9))

        # Tarjeta de progreso (oculta hasta que hay operación)
        self.card_progress = self._card(body)
        self.progress_title = tk.Label(self.card_progress, text="",
                                       font=fonts["big"], bg=THEME["card"],
                                       fg=THEME["text"], anchor="w")
        self.progress_title.pack(fill="x", padx=18, pady=(12, 8))
        self.bar_canvas = tk.Canvas(self.card_progress, height=26, bg=THEME["card"],
                                    highlightthickness=0)
        self.bar_canvas.pack(fill="x", padx=18)
        self.bar_canvas.bind("<Configure>", self._draw_bar)
        self._bar_pct = 0.0
        self.progress_file = tk.Label(self.card_progress, text="", font=fonts["body"],
                                      bg=THEME["card"], fg=THEME["text"], anchor="w")
        self.progress_file.pack(fill="x", padx=18, pady=(8, 0))
        self.progress_info = tk.Label(self.card_progress, text="", font=fonts["small"],
                                      bg=THEME["card"], fg=THEME["muted"], anchor="w")
        self.progress_info.pack(fill="x", padx=18, pady=(0, 6))
        self.cancel_btn = self._flat_button(self.card_progress, "Cancelar",
                                            self._on_cancel, danger=True)
        self.cancel_btn.pack(anchor="e", padx=18, pady=(0, 12))

        # Botón principal (su acción se reasigna dinámicamente según el estado)
        self.primary_btn = self._primary_button(body, "COMPROBAR", self._on_check)
        self.primary_btn.pack(fill="x", pady=(14, 8), ipady=10)

        # Botones secundarios
        row2 = tk.Frame(body, bg=THEME["bg"])
        row2.pack(fill="x")
        self.btn_check = self._secondary_button(row2, "↻  Buscar actualizaciones", self._on_check)
        self.btn_repair = self._secondary_button(row2, "🛠  Reparar", self._on_repair)
        self.btn_folder = self._secondary_button(row2, "📁  Abrir carpeta de mods", self._on_open_folder)
        self.btn_change = self._secondary_button(row2, "… Cambiar carpeta", self._on_change_folder)
        for b in (self.btn_check, self.btn_repair, self.btn_folder, self.btn_change):
            b.pack(side="left", fill="x", expand=True, padx=(0, 6), ipady=6)

        # Pie
        footer = tk.Frame(self.root, bg=THEME["bg"])
        footer.pack(fill="x", padx=18, pady=(4, 10))
        self.conn_dot = tk.Canvas(footer, width=10, height=10, bg=THEME["bg"],
                                  highlightthickness=0)
        self.conn_dot.pack(side="left", pady=4)
        self.conn_label = tk.Label(footer, text="Sin conexión", font=fonts["small"],
                                   bg=THEME["bg"], fg=THEME["muted"])
        self.conn_label.pack(side="left", padx=(4, 0))
        self.ver_label = tk.Label(footer, text=f"ExoVerse Updater v{CONFIG['app_version']}",
                                  font=fonts["small"], bg=THEME["bg"], fg=THEME["muted"])
        self.ver_label.pack(side="right")
        self._set_connection(False)

    def _card(self, parent: tk.Widget) -> tk.Frame:
        f = tk.Frame(parent, bg=THEME["card"], highlightbackground=THEME["card_border"],
                     highlightthickness=1, bd=0)
        return f

    def _flat_button(self, parent: tk.Widget, text: str, cmd: Callable,
                     danger: bool = False) -> tk.Button:
        bg = "#3a2430" if danger else THEME["card_border"]
        fg = THEME["err"] if danger else THEME["text"]
        b = tk.Button(parent, text=text, command=cmd, font=("Segoe UI", 10, "bold"),
                      bg=bg, fg=fg, activebackground=bg, activeforeground=fg,
                      bd=0, relief="flat", highlightthickness=0, cursor="hand2",
                      padx=12, pady=4)
        b._base_bg = bg  # type: ignore[attr-defined]
        b._base_fg = fg  # type: ignore[attr-defined]
        return b

    def _secondary_button(self, parent: tk.Widget, text: str, cmd: Callable) -> tk.Button:
        b = tk.Button(parent, text=text, command=cmd, font=("Segoe UI", 9, "bold"),
                      bg=THEME["card_border"], fg=THEME["text"],
                      activebackground=THEME["card_border"], activeforeground=THEME["text"],
                      bd=0, relief="flat", highlightthickness=0, cursor="hand2")
        b._base_bg = THEME["card_border"]  # type: ignore[attr-defined]
        return b

    def _primary_button(self, parent: tk.Widget, text: str, cmd: Callable) -> tk.Button:
        b = tk.Button(parent, text=text, command=cmd, font=("Segoe UI", 13, "bold"),
                      bg=THEME["accent"], fg="#ffffff",
                      activebackground=THEME["accent_hover"], activeforeground="#ffffff",
                      bd=0, relief="flat", highlightthickness=0, cursor="hand2")
        b._base_bg = THEME["accent"]  # type: ignore[attr-defined]
        b.bind("<Enter>", lambda e: self._hover(b, True))
        b.bind("<Leave>", lambda e: self._hover(b, False))
        return b

    def _hover(self, btn: tk.Button, on: bool) -> None:
        if str(btn["state"]) == "disabled":
            return
        btn.configure(bg=THEME["accent_hover"] if on else btn._base_bg)  # type: ignore[attr-defined]

    def _draw_header(self, event: Optional[tk.Event] = None) -> None:
        c = self.header
        w = c.winfo_width() or 640
        h = c.winfo_height() or 118
        c.delete("all")
        # degradado vertical azul profundo → morado
        top, bot = "#1b2a52", "#0d1220"
        for y in range(h):
            t = y / max(1, h - 1)
            r = int(top[1:3], 16) + (int(bot[1:3], 16) - int(top[1:3], 16)) * t
            g = int(top[3:5], 16) + (int(bot[3:5], 16) - int(top[3:5], 16)) * t
            b = int(top[5:7], 16) + (int(bot[5:7], 16) - int(top[5:7], 16)) * t
            c.create_line(0, y, w, y, fill=f"#{int(r):02x}{int(g):02x}{int(b):02x}")
        # planeta decorativo
        px, py, pr = w - 92, 66, 30
        c.create_oval(px - pr, py - pr, px + pr, py + pr, fill="#3a5ad8", outline="")
        c.create_oval(px - 20, py - 20, px + 4, py + 4, fill="#9db8ff", outline="")
        c.create_oval(px - pr - 16, py - 12, px + pr + 16, py + 12,
                      outline="#6f8dff", width=3)
        for sx, sy in [(60, 30), (150, 22), (210, 44), (120, 92), (300, 26), (380, 18),
                       (430, 50), (250, 100), (520, 30), (560, 80), (70, 70)]:
            c.create_oval(sx, sy, sx + 2, sy + 2, fill="#cfe0ff", outline="")
        c.create_text(36, 44, text="EXOVERSE", anchor="w", fill="#ffffff",
                      font=("Segoe UI", 30, "bold"))
        c.create_text(38, 82, text=f"MOD UPDATER · {CONFIG['minecraft_version']} · {CONFIG['loader']}",
                      anchor="w", fill="#8b96b0", font=("Segoe UI", 10, "bold"))

    def _draw_bar(self, event: Optional[tk.Event] = None) -> None:
        c = self.bar_canvas
        w = c.winfo_width() or 560
        h = c.winfo_height() or 26
        c.delete("all")
        r = h // 2
        # pista
        c.create_oval(0, 0, h, h, fill="#0b1020", outline="")
        c.create_rectangle(r, 0, w - r, h, fill="#0b1020", outline="")
        c.create_oval(w - h, 0, w, h, fill="#0b1020", outline="")
        # relleno
        fw = max(0.0, min(1.0, self._bar_pct)) * (w - 2)
        if fw > 2:
            c.create_oval(1, 1, h - 1, h - 1, fill=THEME["accent"], outline="")
            c.create_rectangle(r, 1, max(r, fw - r), h - 1, fill=THEME["accent"], outline="")
            if fw > h:
                c.create_oval(min(w - 1, fw - h + 1), 1, min(w - 1, fw + 1), h - 1,
                              fill=THEME["accent"], outline="")
        # texto %
        pct = int(round(self._bar_pct * 100))
        c.create_text(w // 2, h // 2, text=f"{pct}%", fill="#ffffff",
                      font=("Segoe UI", 10, "bold"))

    # ── Arranque ────────────────────────────────────────────────────────
    def _startup(self) -> None:
        self._set_connection(False)
        try:
            folder = self.engine.resolve_mods_folder()
            self.sub_label.configure(text=f"Carpeta de mods: {folder}")
            self._run_async(self.engine.check)
        except UpdaterError as e:
            self._show_error(e)
            self._set_primary("SELECCIONAR CARPETA DE MODS", self._on_change_folder)

    # ── Hilos: motor en background, UI nunca bloqueada ──────────────────
    def _run_async(self, fn: Callable, *args: Any) -> None:
        if self.busy:
            return
        self.busy = True
        self._mc_blocked = False
        self._set_busy_ui(True)

        def runner() -> None:
            try:
                fn(*args)
            except UpdaterError as e:
                self._on_engine_event({"t": "error", "code": e.code, "message": e.message})
            except Exception:
                LOG.exception("error no controlado en operación")
                self._on_engine_event({"t": "error", "code": "UNKNOWN",
                                       "message": friendly_errors()["UNKNOWN"]})
            finally:
                self._on_engine_event({"t": "op_end"})

        threading.Thread(target=runner, daemon=True).start()

    def _on_engine_event(self, ev: Dict[str, Any]) -> None:
        self.ui_queue.put(ev)
        self._schedule_tick()

    def _schedule_tick(self) -> None:
        if self._ticker_scheduled:
            return
        if self.busy or not self.ui_queue.empty():
            self._ticker_scheduled = True
            self.root.after(80, self._tick)

    def _tick(self) -> None:
        self._ticker_scheduled = False
        try:
            while True:
                ev = self.ui_queue.get_nowait()
                self._handle_event(ev)
        except queue.Empty:
            pass
        if self.busy or not self.ui_queue.empty():
            self._schedule_tick()

    # ── Manejo de eventos del motor ─────────────────────────────────────
    def _handle_event(self, ev: Dict[str, Any]) -> None:
        t = ev.get("t")
        if t == "status":
            self._set_status(ev["kind"], ev["text"])
        elif t == "versions":
            self.v_local.configure(text=f"Instalada: {ev['local'] or '—'}")
            self.v_remote.configure(text=f"Última: {ev['remote'] or '—'}")
            self._set_connection(True)
        elif t == "plan":
            self.plan = ev["plan"]
            self._render_plan()
        elif t == "progress":
            self._render_progress(ev)
        elif t == "minecraft_running":
            self._mc_blocked = True
            self.busy = False
            self._set_busy_ui(False)
            self._set_status("err", "Minecraft está ejecutándose.\n"
                                    "Cierra Minecraft antes de actualizar los mods.")
            self._set_primary("REINTENTAR", self._on_update)
            self.cancel_btn.configure(text="Actualizar de todos modos",
                                      command=self._on_force_update)
        elif t == "file_done":
            LOG.info("archivo listo: %s (%s)", ev["name"], hsize(ev["size"]))
        elif t == "done":
            self.plan = None
            self._set_status("ok", "✓ Actualización completada")
            self.sub_label.configure(text=ev["summary"])
            self._hide_progress()
            self._set_primary("COMPROBAR DE NUEVO", self._on_check)
            self._set_connection(True)
        elif t == "error":
            self._show_error(UpdaterError(ev.get("code", "UNKNOWN"), ev.get("message", "")))
        elif t == "op_end":
            self.busy = False
            self._set_busy_ui(False)

    # ── Renderizado de UI ───────────────────────────────────────────────
    def _set_status(self, kind: str, text: str) -> None:
        color = {"ok": THEME["ok"], "warn": THEME["warn"],
                 "err": THEME["err"], "info": THEME["info"]}.get(kind, THEME["text"])
        self.status_label.configure(text=text, fg=color)

    def _set_connection(self, ok: bool) -> None:
        self.conn_dot.delete("all")
        color = THEME["ok"] if ok else THEME["err"]
        self.conn_dot.create_oval(2, 2, 10, 10, fill=color, outline="")
        self.conn_label.configure(text="Conectado con GitHub" if ok
                                   else "Sin conexión")

    def _set_primary(self, text: str, cmd: Callable) -> None:
        self.primary_btn.configure(text=text, command=cmd)
        self.primary_btn._base_bg = THEME["accent"]  # type: ignore[attr-defined]
        self.primary_btn.configure(bg=THEME["accent"])

    def _set_busy_ui(self, busy: bool) -> None:
        state = "disabled" if busy else "normal"
        for b in (self.btn_check, self.btn_repair, self.btn_folder, self.btn_change):
            b.configure(state=state)
        if busy:
            self.primary_btn.configure(state="disabled", bg=THEME["card_border"],
                                       text="TRABAJANDO…")
        elif self._mc_blocked:
            pass  # ya reconfigurado en _handle_event
        else:
            self.primary_btn.configure(state="normal")

    def _render_plan(self) -> None:
        plan = self.plan
        self.changes_frame.pack_forget()
        if not plan or not plan.get("has_changes"):
            self._set_primary("ACTUALIZAR", self._on_update)
            return
        txt = self.changes_text
        txt.configure(state="normal")
        txt.delete("1.0", "end")
        added, updated, removed = plan["added"], plan["updated"], plan["removed"]
        if plan.get("first_install"):
            txt.insert("end", "No se ha encontrado una instalación de ExoVerse.\n", "hdr")
            txt.insert("end", "Se descargarán todos los mods oficiales.\n\n", "head")
        else:
            txt.insert("end", "Cambios encontrados\n\n", "hdr")
        if added:
            txt.insert("end", f"+ {len(added)} mods nuevos\n", "add")
            for fc in added:
                txt.insert("end", f"   + {fc['display']}  ({hsize(fc['size'])})\n", "add")
            txt.insert("end", "\n")
        if updated:
            txt.insert("end", f"↻ {len(updated)} mods actualizados\n", "upd")
            for fc in updated:
                txt.insert("end", f"   ↻ {fc['display']}\n", "upd")
            txt.insert("end", "\n")
        if removed:
            txt.insert("end", f"− {len(removed)} mods eliminados\n", "del")
            for fc in removed:
                txt.insert("end", f"   − {fc['display']}\n", "del")
            txt.insert("end", "\n")
        txt.insert("end", f"Total a descargar: {hsize(plan['total_bytes'])} "
                          f"({len(added) + len(updated)} archivos)", "head")
        txt.configure(state="disabled")
        self.changes_frame.pack(fill="both", expand=True, padx=12, pady=(4, 12))
        if plan.get("first_install"):
            self._set_primary(f"INSTALAR EXOVERSE  ({len(added)} MODS · {hsize(plan['total_bytes'])})",
                              self._on_update)
        else:
            self._set_primary("ACTUALIZAR", self._on_update)

    def _render_progress(self, ev: Dict[str, Any]) -> None:
        self.card_progress.pack(fill="x", pady=(12, 0), before=self.primary_btn)
        total, done = ev["total"], ev["done"]
        if ev["phase"] == "apply":
            self.progress_title.configure(text="Aplicando cambios…")
            self._bar_pct = 1.0
            self.progress_file.configure(text="Finalizando…")
            self.progress_info.configure(text="")
        elif ev["phase"] == "extract":
            self.progress_title.configure(text="Descomprimiendo y verificando…")
            self._bar_pct = (done / total) if total else 0.0
            cur = ev.get("current_name") or ""
            self.progress_file.configure(
                text=f"Extrayendo: {os.path.basename(cur)}" if cur else "Extrayendo…")
            done_files, total_files = ev.get("done_files", 0), ev.get("total_files", 0)
            self.progress_info.configure(
                text=f"{hsize(done)} / {hsize(total)}"
                     f"  ·  archivo {min(done_files + 1, total_files)}/{total_files}")
        else:
            self.progress_title.configure(text="Actualizando ExoVerse…")
            self._bar_pct = (done / total) if total else 0.0
            speed = ev.get("speed", 0.0)
            cur = ev.get("current_name") or ""
            done_files, total_files = ev.get("done_files", 0), ev.get("total_files", 0)
            file_line = f"Descargando: {os.path.basename(cur)}" if cur else ""
            self.progress_file.configure(text=file_line)
            info = (f"{hsize(done)} / {hsize(total)}"
                    + (f"  ·  {hsize(speed)}/s" if speed > 0 else "")
                    + f"  ·  archivo {min(done_files + 1, total_files)}/{total_files}")
            self.progress_info.configure(text=info)
        self._draw_bar()
        self.cancel_btn.configure(text="Cancelar", command=self._on_cancel)

    def _hide_progress(self) -> None:
        self.card_progress.pack_forget()

    def _show_error(self, err: UpdaterError) -> None:
        LOG.error("error %s: %s", err.code, err.message)
        self._set_status("err", "⚠ " + err.message)
        self._set_connection(False)
        if err.code in ("NETWORK", "OFFLINE", "HTTP_OTHER", "HASH_MISMATCH",
                        "SIZE_MISMATCH", "HTTP_403"):
            self._set_primary("REINTENTAR", self._on_update if self.plan else self._on_check)
        elif err.code == "FOLDER_NOT_FOUND":
            self._set_primary("SELECCIONAR CARPETA DE MODS", self._on_change_folder)
        else:
            self._set_primary("BUSCAR ACTUALIZACIONES", self._on_check)

    # ── Acciones de botones ─────────────────────────────────────────────
    def _on_check(self) -> None:
        if self.busy:
            return
        self._hide_progress()
        self._run_async(self.engine.check)

    def _on_update(self) -> None:
        if self.busy:
            return
        if self.plan and self.plan.get("removed"):
            ok = messagebox.askyesno(
                "ExoVerse Updater",
                f"Se eliminarán {len(self.plan['removed'])} mods que ya no forman "
                "parte del pack oficial.\n\n¿Quieres continuar?",
                parent=self.root)
            if not ok:
                return
        self._run_async(self.engine.update)

    def _on_force_update(self) -> None:
        self.engine.force = True
        self._run_async(self.engine.update)

    def _on_repair(self) -> None:
        if self.busy:
            return
        self._hide_progress()
        self._run_async(self.engine.repair)

    def _on_cancel(self) -> None:
        if self.busy:
            self.engine.cancel()
            self._set_status("info", "Cancelando…")
        elif self._mc_blocked:
            self._on_force_update()

    def _on_open_folder(self) -> None:
        if not self.engine.mods_folder:
            self._on_change_folder()
            return
        try:
            open_in_explorer(self.engine.mods_folder)
        except Exception as e:
            LOG.error("no se pudo abrir la carpeta: %s", e)
            messagebox.showerror("ExoVerse Updater",
                                 "No se pudo abrir la carpeta de mods.", parent=self.root)

    def _on_change_folder(self) -> None:
        if self.busy:
            return
        initial = self.engine.mods_folder or os.path.expandvars(r"%APPDATA%\.minecraft")
        folder = filedialog.askdirectory(
            title="Selecciona tu carpeta «mods» de Minecraft",
            initialdir=initial)
        if not folder:
            return
        # Si elige .minecraft en vez de mods, se ajusta solo
        base = os.path.basename(os.path.normpath(folder)).lower()
        if base in (".minecraft", "minecraft"):
            folder = os.path.join(folder, "mods")
        elif base != "mods":
            if not messagebox.askyesno(
                    "ExoVerse Updater",
                    f"La carpeta «{folder}» no se llama «mods».\n\n"
                    "¿Seguro que es tu carpeta de mods de Minecraft?",
                    parent=self.root):
                return
        try:
            self.engine.resolve_mods_folder(folder)
            self.sub_label.configure(text=f"Carpeta de mods: {folder}")
            self._on_check()
        except UpdaterError as e:
            self._show_error(e)

    def _on_close(self) -> None:
        if self.busy:
            if not messagebox.askyesno(
                    "ExoVerse Updater",
                    "Hay una operación en curso. ¿Cancelar y salir?",
                    parent=self.root):
                return
            self.engine.cancel()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


# ---------------------------------------------------------------------------
# 15. MODO CONSOLA / HEADLESS  (pruebas, diagnóstico, CI)
# ---------------------------------------------------------------------------
class ConsoleRunner:
    def __init__(self, source_url: Optional[str] = None,
                 mods_folder: Optional[str] = None, apply: bool = False,
                 skip_mc_check: bool = False):
        self.apply = apply
        self.skip_mc_check = skip_mc_check
        self.engine = UpdaterEngine(emit=self._emit)
        if source_url:
            self.engine.source = RemoteSource(source_url)
        if mods_folder:
            self.engine.resolve_mods_folder(mods_folder)
        if skip_mc_check:
            self.engine.force = True

    def _emit(self, ev: Dict[str, Any]) -> None:
        t = ev.get("t")
        if t == "status":
            print(f"[{ev['kind']}] {ev['text']}")
        elif t == "versions":
            print(f"  versión instalada: {ev['local'] or '—'}  |  última: {ev['remote'] or '—'}")
        elif t == "plan" and ev.get("plan"):
            p = ev["plan"]
            print(f"  plan: +{len(p['added'])} añadidos · ↻{len(p['updated'])} actualizados "
                  f"· -{len(p['removed'])} eliminados · {hsize(p['total_bytes'])} a descargar")
            for fc in p["added"]:
                print(f"    + {fc['rel']}")
            for fc in p["updated"]:
                print(f"    ↻ {fc['rel']}")
            for fc in p["removed"]:
                print(f"    - {fc['rel']}")
        elif t == "progress" and ev.get("total"):
            pct = int(ev["done"] / ev["total"] * 100) if ev["total"] else 0
            print(f"\r  {pct:3d}%  {hsize(ev['done'])}/{hsize(ev['total'])}  "
                  f"{hsize(ev.get('speed', 0))}/s  "
                  f"({ev.get('done_files', 0)}/{ev.get('total_files', 0)})", end="", flush=True)
        elif t == "file_done":
            print(f"\r  ✓ {ev['name']} ({hsize(ev['size'])})        ")
        elif t == "minecraft_running":
            print("  ⚠ Minecraft en ejecución. Cierra el juego antes de actualizar.")
            if not self.skip_mc_check:
                self.engine.force = False
        elif t == "done":
            print(f"\r  ✓ {ev['summary'].replace(chr(10), ' ')}")
        elif t == "error":
            print(f"  ✗ [{ev.get('code')}] {ev.get('message')}")

    def run(self) -> int:
        try:
            plan = self.engine.check()
            if self.apply and plan.has_changes:
                self.engine.force = self.skip_mc_check
                if self.engine.update(plan) == -1:
                    return 3   # Minecraft abierto
            return 0 if not plan.has_changes or self.apply else 2
        except UpdaterError as e:
            print(f"✗ ERROR [{e.code}]: {e.message}")
            return 1
        except Exception:
            LOG.exception("error no controlado")
            print("✗ ERROR: inesperado (revisa exoverse_updater.log)")
            return 1


# ---------------------------------------------------------------------------
# 16. ENTRADA PRINCIPAL
# ---------------------------------------------------------------------------
def cmd_build_manifest(args: argparse.Namespace) -> int:
    """Herramienta del administrador: genera manifest.json desde una carpeta."""
    src = args.src_folder
    out = args.out_manifest
    existing: Optional[Dict[str, Any]] = None
    if os.path.isfile(out):
        try:
            with open(out, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = None
    print(f"Generando manifiesto para «{src}»…")
    try:
        manifest = ManifestManager.build(src, args.new_version, existing,
                                         make_zip=args.zip, zip_out=out)
    except UpdaterError as e:
        print(f"\n✗ {e.message}")
        LOG.error("no se pudo generar el manifiesto: %s", e.message.replace("\n", " "))
        return 1
    atomic_write_json(out, manifest)
    print(f"\n✔ manifest.json generado:")
    print(f"  versión      : {manifest['version']}")
    print(f"  archivos     : {manifest['file_count']}")
    print(f"  tamaño total : {hsize(manifest['total_size'])}")
    if manifest.get("dist") == "zip":
        print(f"  pack         : {manifest['archive']} ({hsize(manifest['archive_size'])})")
    print(f"  destino      : {os.path.abspath(out)}")
    print("\nRevisa los archivos, haz commit y push a GitHub.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="ExoVerseUpdater",
        description="ExoVerse Mod Updater — actualizador de mods para el servidor ExoVerse.",
        add_help=True)
    parser.add_argument("--version", action="version",
                        version=f"ExoVerse Updater v{CONFIG['app_version']}")
    parser.add_argument("--headless", action="store_true",
                        help="modo consola (sin interfaz gráfica)")
    parser.add_argument("--apply", action="store_true",
                        help="(con --headless) aplicar los cambios automáticamente")
    parser.add_argument("--source-url", default=None,
                        help="URL base alternativa (pruebas o futuro hosting)")
    parser.add_argument("--mods-folder", default=None,
                        help="carpeta de mods (pruebas)")
    parser.add_argument("--skip-mc-check", action="store_true",
                        help="(con --headless) no comprobar si Minecraft está abierto")
    parser.add_argument("--build-manifest", action="store_true",
                        help="(administrador) generar manifest.json desde una carpeta")
    parser.add_argument("--src-folder", default="mods",
                        help="carpeta con los mods para --build-manifest (por defecto: mods)")
    parser.add_argument("--out-manifest", default="manifest.json",
                        help="archivo de salida para --build-manifest")
    parser.add_argument("--new-version", default=None,
                        help="versión para --build-manifest (si se omite, auto-incrementa)")
    parser.add_argument("--zip", action="store_true",
                        help="(con --build-manifest) empaquetar los mods en mods.zip "
                             "(modo zip). SIN esta opción se genera en modo carpeta: "
                             "los .jar se suben a la carpeta mods/ del repositorio")
    args = parser.parse_args()

    setup_logging(AppPaths.log_file(), console=args.headless or args.build_manifest)
    LOG.info("═══ %s v%s iniciado (frozen=%s, python=%s) ═══",
             CONFIG["app_name"], CONFIG["app_version"],
             getattr(sys, "frozen", False), sys.version.split()[0])

    if args.build_manifest:
        return cmd_build_manifest(args)

    if args.headless:
        runner = ConsoleRunner(source_url=args.source_url,
                               mods_folder=args.mods_folder,
                               apply=args.apply,
                               skip_mc_check=args.skip_mc_check)
        return runner.run()

    if os.name != "nt":
        print("⚠ La interfaz gráfica está pensada para Windows. "
              "Usa --headless para probar en este sistema.")
        runner = ConsoleRunner(source_url=args.source_url,
                               mods_folder=args.mods_folder,
                               apply=args.apply)
        return runner.run()

    app = ExoVerseApp()
    app.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
