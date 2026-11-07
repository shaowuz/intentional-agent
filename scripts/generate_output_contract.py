"""Refresh the visualization team's schema/types from the canonical exporter. No model calls."""
from pathlib import Path
from swarm_game.export_contract import schema, typescript
from swarm_game.storage import write_json

if __name__ == '__main__':
    output = Path(__file__).resolve().parents[1] / 'docs' / 'visualization'
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / 'visualization.schema.json', schema())
    (output / 'types.ts').write_text(typescript(), encoding='utf-8')
