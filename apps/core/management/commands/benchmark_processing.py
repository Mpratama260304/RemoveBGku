import io
import time
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from PIL import Image

from apps.jobs.tasks import get_rembg_session


class Command(BaseCommand):
    help = "Benchmark lokal satu model rembg tanpa membuat ImageJob."

    def add_arguments(self, parser):
        parser.add_argument("--input", required=True)
        parser.add_argument("--runs", type=int, default=3)
        parser.add_argument("--model", default="u2netp")

    def handle(self, *args, **options):
        path = Path(options["input"])
        if not path.is_file():
            raise CommandError("File input tidak ditemukan.")
        raw = path.read_bytes()
        with Image.open(io.BytesIO(raw)) as image:
            dimensions = image.size
        started = time.monotonic()
        session = get_rembg_session(options["model"])
        load_seconds = time.monotonic() - started
        from rembg import remove

        durations = []
        result = b""
        for _ in range(max(1, options["runs"])):
            started = time.monotonic()
            result = remove(raw, session=session, force_return_bytes=True)
            durations.append(time.monotonic() - started)
        self.stdout.write(f"Model: {options['model']}")
        self.stdout.write(f"Load model: {load_seconds:.3f} detik")
        self.stdout.write(f"Waktu proses: {', '.join(f'{d:.3f}' for d in durations)} detik")
        self.stdout.write(f"Input: {len(raw)} byte, {dimensions[0]}x{dimensions[1]}")
        self.stdout.write(f"Output: {len(result)} byte")
