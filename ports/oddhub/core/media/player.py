"""Player de mídia externo (mpv preferido, ffplay fallback)."""
import shutil
import subprocess


def available():
    return shutil.which("mpv") or shutil.which("ffplay")


def play(url, fullscreen=True):
    """Inicia reprodução e retorna o processo (ou None)."""
    mpv = shutil.which("mpv")
    if mpv:
        args = [mpv, url]
        if fullscreen:
            args += ["--fullscreen", "--force-window=yes"]
        return subprocess.Popen(args)
    ff = shutil.which("ffplay")
    if ff:
        args = [ff, "-autoexit"]
        if fullscreen:
            args += ["-fs"]
        args.append(url)
        return subprocess.Popen(args)
    return None