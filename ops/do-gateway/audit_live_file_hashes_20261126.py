"""Read-only: print git blob hashes of the deployed app's backend files and
the gaemigtp systemd units, so the repository can be synced to the server."""
import hashlib
import pathlib

APP = pathlib.Path("/opt/gaemigtp-news/app")
UNITS = pathlib.Path("/etc/systemd/system")


def blob(path):
    raw = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


def main():
    for path in sorted(APP.glob("backend/**/*.py")) + sorted(APP.glob("*.py")):
        if path.is_file() and not path.is_symlink() and "__pycache__" not in path.parts:
            print("APP %s %s" % (blob(path), path.relative_to(APP)), flush=True)
    for path in sorted(UNITS.glob("gaemigtp-*")):
        if path.is_file() and not path.is_symlink():
            print("UNIT %s %s" % (blob(path), path.name), flush=True)


if __name__ == "__main__":
    main()
