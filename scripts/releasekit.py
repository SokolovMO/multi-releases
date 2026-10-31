"""Serialized public delivery commands; only GitHub Actions may invoke mutations."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
from release_manifest import create, verify

APPS = {"MultiShift": "SokolovMO/MultiShift", "MultiSwitcher": "SokolovMO/MultiSwitcher"}
DEST = "SokolovMO/multi-releases"
NS = "http://www.andymatuschak.org/xml-namespaces/sparkle"
ET.register_namespace("sparkle", NS)


def gh(*args, data=None):
    result = subprocess.run(["gh", *args], input=json.dumps(data) if data is not None else None,
                            text=True, capture_output=True, check=True)
    return json.loads(result.stdout) if result.stdout.strip() else None


def api(path, method="GET", data=None):
    args = ["api", path, "--method", method]
    if data is not None:
        args += ["--input", "-"]
    return gh(*args, data=data)


def releases(repo):
    pages = gh("api", f"repos/{repo}/releases?per_page=100", "--paginate", "--slurp")
    return [release for page in pages for release in page]


def download(repo, release, name, directory):
    assets = [a for a in release["assets"] if a["name"] == name]
    if len(assets) != 1 or Path(name).name != name:
        raise ValueError("required unique asset missing or invalid")
    # gh downloads private assets through authenticated API; no credentials in URLs.
    subprocess.run(["gh", "release", "download", release["tag_name"], "--repo", repo,
                    "--pattern", name, "--dir", str(directory), "--clobber"], check=True,
                   stdout=subprocess.DEVNULL)
    return Path(directory) / name


def find(repo, tag):
    return api(f"repos/{repo}/releases/tags/{tag}")


def validate_tag(tag, channel, version, build):
    expected = f"{'beta-v' if channel == 'beta' else 'v'}{version}-build{build}"
    if tag != expected or not re.fullmatch(r"(?:beta-)?v\d+\.\d+\.\d+-build[1-9]\d*", tag):
        raise ValueError("release tag does not match manifest")


def load_candidate(app, release, repo, directory):
    manifest = json.loads(download(repo, release, "manifest.json", directory).read_text())
    if manifest["app"] != app or manifest["architecture"] != "arm64":
        raise ValueError("candidate app/architecture mismatch")
    validate_tag(release["tag_name"].removeprefix(app + "-"), manifest["channel"], manifest["version"], manifest["build"])
    artifact = download(repo, release, manifest["artifact"], directory)
    return manifest, artifact


def publish(app, tag, expected, acceptance):
    source = APPS[app]
    release = find(source, tag)
    with tempfile.TemporaryDirectory() as temp:
        manifest, artifact = load_candidate(app, release, source, temp)
        if manifest["candidate_id"] != expected:
            raise ValueError("candidate identity changed")
        verify(manifest, artifact, acceptance)
        if manifest.get("updater_public_key") != os.environ[app.upper() + "_SPARKLE_PUBLIC_KEY"]:
            raise ValueError("candidate updater public key does not match delivery key")
        if release["prerelease"] != (manifest["channel"] == "beta"):
            raise ValueError("channel mismatch")
        public_tag = app + "-" + tag
        existing = [r for r in releases(DEST) if r["tag_name"] == public_tag]
        if existing:
            # Idempotent retries are allowed only for the same immutable artifact.
            existing_manifest = json.loads(download(DEST, existing[0], "manifest.json", temp).read_text())
            if existing_manifest != manifest:
                raise ValueError("public tag already bound to another artifact")
            if not existing[0]["draft"]:
                return
        else:
            # Never publish an old draft over a newer build on the same channel.
            for previous in releases(DEST):
                if previous["draft"] or not previous["tag_name"].startswith(app + "-"):
                    continue
                with tempfile.TemporaryDirectory() as older:
                    old = json.loads(download(DEST, previous, "manifest.json", older).read_text())
                if old["channel"] == manifest["channel"] and int(old["build"]) >= int(manifest["build"]):
                    raise ValueError("build number must increase within the channel")
            args = ["gh", "release", "create", public_tag, "--repo", DEST, "--draft", "--title", f"{app} {manifest['version']} ({manifest['channel']})"]
            if release["prerelease"]:
                args.append("--prerelease")
            subprocess.run(args, check=True)
        acceptance_path = Path(temp) / "acceptance.json"
        acceptance_path.write_text(json.dumps(acceptance, indent=2))
        files = [artifact, Path(temp) / "manifest.json", acceptance_path]
        # MultiShift is AGPL: distribute exact corresponding source and notices too.
        for name in ("source.tar.gz", "THIRD-PARTY-NOTICES.md", "LICENSE"):
            files.append(download(source, release, name, temp))
        subprocess.run(["gh", "release", "upload", public_tag, "--repo", DEST, "--clobber", *map(str, files)], check=True)
        public = find(DEST, public_tag)
        api(f"repos/{DEST}/releases/{public['id']}", "PATCH", {"draft": False, "make_latest": "false"})


def withdraw(app, tag):
    if not tag.startswith(app + "-"):
        raise ValueError("release belongs to another application")
    release = find(DEST, tag)
    api(f"repos/{DEST}/releases/{release['id']}", "PATCH", {"draft": True})


def sign(binary, key, path, signature_only=False):
    args = [binary, "--ed-key-file", "-"]
    if signature_only:
        args.append("-p")
    args.append(str(path))
    result = subprocess.run(args, input=key, capture_output=True, check=True)
    return result.stdout.decode().strip()


def render_feed(app, items):
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = app
    ET.SubElement(channel, "description").text = "Signed updates for " + app
    ET.SubElement(channel, "link").text = f"https://sokolovmo.github.io/multi-releases/{app}/"
    for manifest, url, length, signature in sorted(items, key=lambda i: int(i[0]["build"]), reverse=True):
        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = f"{app} {manifest['version']}"
        for name, value in (("version", manifest["build"]), ("shortVersionString", manifest["version"]),
                            ("minimumSystemVersion", manifest["minimum_macos"])):
            ET.SubElement(item, f"{{{NS}}}{name}").text = value
        if manifest["channel"] == "beta":
            ET.SubElement(item, f"{{{NS}}}channel").text = "beta"
        ET.SubElement(item, "link").text = url.rsplit("/", 1)[0].replace("/download/", "/tag/")
        ET.SubElement(item, "enclosure", {"url": url, "length": str(length), "type": "application/octet-stream",
                                         f"{{{NS}}}edSignature": signature, f"{{{NS}}}os": "macos", f"{{{NS}}}cpuArchitecture": "arm64"})
    return ET.tostring(rss, encoding="utf-8", xml_declaration=True)


def feeds(output, binary):
    published = [r for r in releases(DEST) if not r["draft"]]
    for app in APPS:
        key = base64.b64decode(os.environ[app.upper() + "_SPARKLE_PRIVATE_KEY_BASE64"], validate=True)
        items = []
        summaries = []
        for release in published:
            if not release["tag_name"].startswith(app + "-"):
                continue
            with tempfile.TemporaryDirectory() as temp:
                manifest, artifact = load_candidate(app, release, DEST, temp)
                acceptance = json.loads(download(DEST, release, "acceptance.json", temp).read_text())
                verify(manifest, artifact, acceptance)
                if manifest.get("updater_public_key") != os.environ[app.upper() + "_SPARKLE_PUBLIC_KEY"]:
                    raise ValueError("published updater public key mismatch")
                if release["prerelease"] != (manifest["channel"] == "beta"):
                    raise ValueError("public channel mismatch")
                url = f"https://github.com/{DEST}/releases/download/{release['tag_name']}/{artifact.name}"
                signature = sign(binary, key, artifact, True)
                items.append((manifest, url, artifact.stat().st_size, signature))
                summaries.append({**manifest, "url": url, "release_url": release["html_url"]})
        directory = Path(output) / app
        directory.mkdir(parents=True, exist_ok=True)
        feed = directory / "appcast.xml"
        feed.write_bytes(render_feed(app, items))
        sign(binary, key, feed)
        (directory / "releases.json").write_text(json.dumps(sorted(summaries, key=lambda m: int(m["build"]), reverse=True), indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["publish", "withdraw", "feeds"])
    parser.add_argument("--app", choices=list(APPS))
    parser.add_argument("--tag")
    parser.add_argument("--candidate-id")
    parser.add_argument("--acceptance")
    parser.add_argument("--output", default="site")
    parser.add_argument("--sign-update")
    args = parser.parse_args()
    if args.command == "feeds":
        feeds(args.output, args.sign_update)
    elif args.command == "publish":
        publish(args.app, args.tag, args.candidate_id, json.loads(args.acceptance))
    else:
        withdraw(args.app, args.tag)

if __name__ == "__main__":
    main()
