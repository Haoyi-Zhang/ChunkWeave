"""Draw the callback-shadow example directly as an embedded-font vector PDF."""
from pathlib import Path
import argparse
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch, FancyArrowPatch


def draw(output):
    plt.rcParams.update({'font.family': 'STIXGeneral', 'font.size': 8.6,
                         'pdf.fonttype': 42, 'ps.fonttype': 42,
                         'text.usetex': False, 'axes.unicode_minus': False})
    fig = plt.figure(figsize=(110 / 25.4, 55 / 25.4))
    ax = fig.add_axes([0, 0, 1, 1], xlim=(-.9, 10.1), ylim=(-.15, 5.35))
    ax.axis('off')
    labels = []

    def text(x, y, value, **kw):
        bounds = kw.pop('bounds', None)
        obj = ax.text(x, y, value, ha=kw.pop('ha', 'center'), va='center',
                      linespacing=1.05, zorder=3, **kw)
        labels.append((obj, bounds))

    def arrow(a, b):
        ax.add_patch(FancyArrowPatch(a, b, arrowstyle='-|>', mutation_scale=7,
                                    linewidth=.6, color='black', shrinkA=0, shrinkB=0))

    for left, right, label in [
        (1.15, 3.45, 'data:a'), (3.45, 4.20, 'LF LF'),
        (4.20, 5.45, 'data:'), (5.45, 5.95, 'E4'),
        (5.95, 6.45, 'B8'), (6.45, 6.95, 'AD'), (6.95, 7.80, 'LF LF'),
    ]:
        ax.add_patch(Rectangle((left, 3.70), right-left, .4,
                               facecolor='white', edgecolor='black', linewidth=.6))
        text((left+right)/2, 3.90, label)
    for x, value in [(1.15, 0), (4.20, 8), (5.45, 13), (5.95, 14), (6.95, 16), (7.80, 18)]:
        ax.plot([x, x], [3.70, 3.61], color='black', linewidth=.6)
        text(x, 3.43, str(value), fontsize=8)
    for x, label in [(4.20, 'event 1\ncommit'), (5.95, 'transport\ncut')]:
        arrow((x, 4.38), (x, 4.13))
        text(x, 4.75, label, fontsize=8)

    rows = [
        (2.10, 'Immediate', ['decode\n[0,14)\nresidual E4', 'callback 1\nreplace now',
                            'decode\n[14,18)\norphan B8 AD', 'wrong\nevent 2']),
        (.75, 'CommitGate', ['decode\n[0,14)\nresidual E4', 'callback 1\nqueue\nrequest',
                            'finish scalar\nE4 B8 AD', 'replace\nafter\nscalar']),
    ]
    centers = [2.05, 4.10, 6.25, 8.15]
    widths = [1.66, 1.61, 2.06, 1.11]
    for y, title, values in rows:
        text(1, y, title, ha='right', fontweight='bold')
        for x, width, value in zip(centers, widths, values):
            ax.add_patch(FancyBboxPatch((x-width/2, y-.60), width, 1.20,
                                       boxstyle='round,pad=0,rounding_size=.04',
                                       facecolor='white', edgecolor='black', linewidth=.6))
            text(x, y, value, bounds=(x-width/2+.025, y-.58, x+width/2-.025, y+.58))
        for x, a, z, b in zip(centers, widths, centers[1:], widths[1:]):
            arrow((x+a/2, y), (z-b/2, y))
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    for label, bounds in labels:
        b = label.get_window_extent(renderer).transformed(ax.transData.inverted())
        if b.x0 < -.88 or b.x1 > 10.08 or b.y0 < -.13 or b.y1 > 5.33:
            raise ValueError('Clipped callback label: ' + label.get_text())
        if bounds and (b.x0 < bounds[0] or b.y0 < bounds[1] or b.x1 > bounds[2] or b.y1 > bounds[3]):
            raise ValueError('Callback label exceeds its box: ' + label.get_text())
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, metadata={'Creator': 'Python Matplotlib', 'Producer': None,
                                  'CreationDate': None, 'ModDate': None})
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path,
                    default=Path(__file__).resolve().parents[1]/'figures/shadow.pdf')
    args = ap.parse_args()
    draw(args.output)
    print('Callback example drawn; no experiment executed.')


if __name__ == '__main__':
    main()
