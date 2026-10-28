#!/usr/bin/env python3
"""Compare OpenFOAM log forces: plot_forces.py file1.txt [file2.txt ...].
Writes a standalone SVG; no third-party packages required.
"""
import argparse
import colorsys
import html
import re
from pathlib import Path

NUMBER = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?'
TIME = re.compile(r'^\s*Time\s*=\s*(' + NUMBER + r')\s*$')
VECTOR = re.compile(r'^\s*(Total|Pressure|Viscous)\s*:\s*\(\s*(' + NUMBER + r')\s+(' + NUMBER + r')\s+(' + NUMBER + r')\s*\)')


def read_forces(filename, kind):
    samples, time, in_forces = [], None, False
    with filename.open(errors='replace') as stream:
        for line in stream:
            match = TIME.match(line)
            if match:
                time, in_forces = float(match[1]), False
            elif line.strip() == 'Sum of forces':
                in_forces = True
            elif line.strip() == 'Sum of moments':
                in_forces = False
            elif in_forces and time is not None:
                match = VECTOR.match(line)
                if match and match[1].lower() == kind:
                    samples.append((time, *(float(match[i]) for i in (2, 3, 4))))
    return samples


def render_svg(series, kind):
    left, plot_width, panel_height = 120, 820, 180
    top = 65 + 25 * len(series)
    height = top + 710
    all_samples = [sample for _, samples in series for sample in samples]
    xmin, xmax = min(s[0] for s in all_samples), max(s[0] for s in all_samples)
    if xmin == xmax:
        xmin, xmax = xmin - 0.5, xmax + 0.5
    palette = ['#2563eb', '#dc2626', '#059669', '#9333ea', '#ea580c', '#0891b2']
    colors = [palette[i] if i < len(palette) else '#%02x%02x%02x' % tuple(int(c * 255) for c in colorsys.hsv_to_rgb((i * 0.618) % 1, 0.75, 0.7)) for i in range(len(series))]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="{height}" viewBox="0 0 1000 {height}">',
           '<rect width="100%" height="100%" fill="white"/>',
           '<g font-family="sans-serif" font-size="13" fill="#222">',
           f'<text x="500" y="28" text-anchor="middle" font-size="18">{kind.capitalize()} forces vs simulation time</text>']
    for i, ((label, _), color) in enumerate(zip(series, colors)):
        y = 52 + 25 * i
        out.append(f'<path d="M120,{y} h30" stroke="{color}" stroke-width="2"/><text x="160" y="{y+4}">{html.escape(label)}</text>')
    for component, axis in enumerate('xyz', 1):
        ytop = top + (component - 1) * 235
        values = [s[component] for s in all_samples]
        low, high = min(values), max(values)
        padding = (high - low) * 0.08 if high != low else max(abs(low) * 0.05, 1e-12)
        low, high = low - padding, high + padding
        def px(value):
            return left + (value - xmin) / (xmax - xmin) * plot_width
        def py(value):
            return ytop + panel_height - (value - low) / (high - low) * panel_height
        for tick in range(6):
            x, y = left + tick * plot_width / 5, ytop + tick * panel_height / 5
            out.extend([
                f'<path d="M{x},{ytop} v{panel_height} M{left},{y} h{plot_width}" stroke="#e5e7eb" fill="none"/>',
                f'<text x="{x}" y="{ytop+panel_height+20}" text-anchor="middle">{xmin+tick*(xmax-xmin)/5:.5g}</text>',
                f'<text x="{left-10}" y="{y+4}" text-anchor="end">{high-tick*(high-low)/5:.5g}</text>'])
        out.append(f'<rect x="{left}" y="{ytop}" width="{plot_width}" height="{panel_height}" fill="none" stroke="#999"/>')
        for (_, samples), color in zip(series, colors):
            points = ' '.join(f'{px(s[0]):.3f},{py(s[component]):.3f}' for s in samples)
            out.append(f'<polyline points="{points}" stroke="{color}" stroke-width="1.8" fill="none"/>')
            for sample in samples:
                out.append(f'<circle cx="{px(sample[0]):.3f}" cy="{py(sample[component]):.3f}" r="2.5" fill="{color}"/>')
        out.append(f'<text x="{left}" y="{ytop-12}">F{axis} (N)</text>')
    out.append(f'<text x="530" y="{height-15}" text-anchor="middle">Simulation time (s)</text></g></svg>')
    return '\n'.join(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('filenames', nargs='+', type=Path, help='OpenFOAM log files; shell wildcards supported')
    parser.add_argument('--kind', choices=['total', 'pressure', 'viscous'], default='total')
    parser.add_argument('-o', '--output', type=Path, help='SVG output path')
    args = parser.parse_args()
    try:
        series = []
        names = [p.name for p in args.filenames]
        for path in args.filenames:
            samples = read_forces(path, args.kind)
            if not samples:
                parser.error(f'No {args.kind} force samples with simulation times found in {path}')
            series.append((path.name if names.count(path.name) == 1 else str(path), samples))
        output = args.output or Path(f'{args.filenames[0].stem}_forces.svg' if len(series) == 1 else 'forces_comparison.svg')
        if output.resolve() in [p.resolve() for p in args.filenames]:
            parser.error('Output must differ from every input')
        output.write_text(render_svg(series, args.kind), encoding='utf-8')
    except OSError as error:
        parser.exit(1, f'Error: {error}\n')
    print(f'Saved {output}')
    for label, samples in series:
        print(f'  {label}: {len(samples)} samples, time {samples[0][0]:g}–{samples[-1][0]:g} s')


if __name__ == '__main__':
    main()
