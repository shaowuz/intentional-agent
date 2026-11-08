"""Verify every archived byte; optionally extract safely or replay without model calls."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sys
import tarfile

sys.dont_write_bytecode = True


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as file:
        for block in iter(lambda: file.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def verify_archive(package, destination=None):
    manifest = json.loads((package / 'archive-manifest.json').read_text())
    archive = package / manifest['archive']['path']
    if sha256(archive) != manifest['archive']['sha256']:
        raise ValueError('Archive SHA-256 mismatch')
    expected = {row['path']: row for row in manifest['files']}
    if len(expected) != len(manifest['files']):
        raise ValueError('Duplicate manifest path')
    prefix = manifest['archive']['root']
    if destination is not None:
        destination = destination.resolve()
        destination.mkdir(parents=True, exist_ok=False)
    seen = set()
    total = 0
    with tarfile.open(archive, 'r|xz') as tar:
        for member in tar:
            path = PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or path.parts[0] != prefix:
                raise ValueError('Unsafe archive member path')
            if not (member.isdir() or member.isreg()):
                raise ValueError('Only directories and regular files may be extracted')
            target = destination.joinpath(*path.parts) if destination is not None else None
            if member.isdir():
                if target is not None:
                    target.mkdir(parents=True, exist_ok=True)
                continue
            relative = PurePosixPath(*path.parts[1:]).as_posix()
            if relative not in expected or relative in seen:
                raise ValueError('Unexpected or duplicate archive member: ' + relative)
            row = expected[relative]
            if member.size != row['bytes']:
                raise ValueError('Member size differs: ' + relative)
            file = tar.extractfile(member)
            if file is None:
                raise ValueError('Unreadable archive member')
            output = None
            if target is not None:
                target.parent.mkdir(parents=True, exist_ok=True)
                output = target.open('xb')
            digest = hashlib.sha256()
            try:
                for block in iter(lambda: file.read(1024 * 1024), b''):
                    digest.update(block)
                    if output is not None:
                        output.write(block)
            finally:
                file.close()
                if output is not None:
                    output.close()
            if digest.hexdigest() != row['sha256']:
                raise ValueError('Member SHA-256 differs: ' + relative)
            if target is not None:
                target.chmod(member.mode & 0o777)
                os.utime(target, (member.mtime, member.mtime))
            seen.add(relative)
            total += member.size
    if seen != set(expected) or len(seen) != manifest['archive']['files']:
        raise ValueError('Archive file inventory differs from manifest')
    if total != manifest['archive']['uncompressed_file_bytes']:
        raise ValueError('Uncompressed file-byte total differs')
    for relative in manifest['expanded_files']:
        if sha256(package / relative) != expected[relative]['sha256']:
            raise ValueError('Expanded review copy differs: ' + relative)
    return {'status': 'valid', 'archive_sha256': manifest['archive']['sha256'],
            'files_verified': len(seen), 'uncompressed_file_bytes': total,
            'expanded_files_verified': len(manifest['expanded_files']),
            'extracted_output': str(destination / prefix) if destination is not None else None}


def replay(output, *, allow_python_version_difference=False):
    output = output.resolve()
    sys.path.insert(0, str(output / 'runtime'))
    import swarm_game
    from swarm_game.config import Config
    from swarm_game.export_contract import validate_output
    from swarm_game.game import commit_phase, initial_state
    from swarm_game.protocol import make_request, validate_response
    from swarm_game.storage import provenance, read_json

    if Path(swarm_game.__file__).parent.resolve() != output / 'runtime/swarm_game':
        raise ValueError('Replay must import the archived frozen runtime')
    manifest = read_json(output / 'matrix_manifest.json')
    current, recorded = provenance(), manifest['provenance']
    comparison_current, comparison_recorded = dict(current), dict(recorded)
    if allow_python_version_difference:
        comparison_current.pop('python')
        comparison_recorded.pop('python')
    if comparison_current != comparison_recorded:
        raise ValueError('Replay requires matching frozen source and dependencies; Python must also match unless explicitly allowed')
    requests = 0
    for entry in manifest['plan']:
        episode = output / 'episodes' / entry['episode_id']
        config = Config(**entry['config'])
        saved = read_json(episode / 'checkpoint.json')
        if not saved['completed']:
            raise ValueError('Incomplete episode: ' + entry['episode_id'])
        state = initial_state(config)
        calls = 0
        while not state['completed']:
            for player in state['players']:
                request = make_request(state, config, player)
                call_id = f"{state['round']:04d}-{state['phase']}-{player}"
                record = read_json(episode / 'requests' / (call_id + '.json'))
                if record['request'] != request.to_dict() or not record['complete']:
                    raise ValueError('Saved request or completion mismatch: ' + call_id)
                state['pending'][player] = validate_response(record['data'], request, config)
                calls += 1
            commit_phase(state, config)
        if state != saved or calls != config.expected_requests:
            raise ValueError('Reconstructed checkpoint differs: ' + entry['episode_id'])
        requests += calls
    return {'status': 'passed', 'episodes': len(manifest['plan']),
            'accepted_requests': requests, 'hosted_calls': 0,
            'recorded_python': recorded['python'], 'replay_python': current['python'],
            'python_version_difference_allowed': allow_python_version_difference,
            'output_contract': validate_output(output)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--extract', type=Path, help='new directory; existing paths are never overwritten')
    parser.add_argument('--replay', type=Path, help='extracted output root; requires recorded dependencies')
    parser.add_argument('--allow-python-version-difference', action='store_true',
                        help='Replay under a different Python version; source/dependencies must still match')
    args = parser.parse_args()
    result = {'archive': verify_archive(Path(__file__).resolve().parent, args.extract)}
    print(json.dumps(result, indent=2), flush=True)
    if args.replay is not None:
        result['replay'] = replay(args.replay, allow_python_version_difference=args.allow_python_version_difference)
        print(json.dumps({'replay': result['replay']}, indent=2), flush=True)


if __name__ == '__main__':
    main()
