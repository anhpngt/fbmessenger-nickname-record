import argparse
import json
import os
import re
from collections import Counter
from typing import Any
from typing import Dict
from typing import List
from typing import Optional


class FBNicknameFinder:
    MATCH_PHRASE = ' set your nickname to '
    _PHRASE_OFFSET = len(MATCH_PHRASE)
    _REGEX = re.compile(MATCH_PHRASE + r'.+\Z')

    def __init__(self):
        self.username = None        # type: Optional[str]

    def setUsername(self, username: Optional[str]) -> None:
        if username:
            print(f'INFO: Skipping messages from {username}')
            self.username = self._unfixMojibake(username)

    def findInFiles(self, files: List[str]) -> None:
        self._initProcess()
        for f in files:
            if not os.path.isfile(f):
                print(f'WARN: Ignoring file {f} (not a file)')
                continue

            self._findInFile(f)

    def findInDirectory(self, path: str) -> None:
        self._initProcess()

        if not os.path.isdir(path):
            print(f'FATAL: Invalid input directory ({path})')
            return

        for f in os.listdir(path):
            self._findInFile(os.path.join(path, f))

    def printResult(self) -> None:
        distinctNames = Counter(item['nickname'] for item in self._result)
        print(f'Found {len(distinctNames)} nicknames:')
        for name, count in distinctNames.items():
            print(f'\t{name}' + ('' if count == 1 else f' ({count} times)'))

    def writeResult(self, outfile: str) -> None:
        with open(outfile, 'w') as fd:
            json.dump({'result': self._result,
                       'length': len(self._result)},
                      fd, ensure_ascii=False, indent=4)

    def _initProcess(self):
        self._result = []           # type: List[Dict[str, Any]]
        self.crashed = False        # type: bool

    def _findInFile(self, f: str) -> None:
        try:
            with open(f, 'r') as fd:
                jdata = json.load(fd)
        except Exception:
            print(f'WARN: Ignoring file {f} (not a valid JSON file)')
            return

        try:
            # Skip if not participant of current conversation
            if self.username and not self._isParticipant(jdata['participants']):
                return

            for m in jdata['messages']:
                # Skip messages from your own
                if self.username and m['sender_name'] == self.username:
                    continue

                # Skip non-Generic messages (e.g. Share types)
                # and messages sending media/stickers/etc..
                if m['type'] != 'Generic' or 'content' not in m:
                    continue

                regexResult = self._REGEX.search(m['content'])
                if regexResult and regexResult.start() > 0:
                    # Matches "<username1> has set your nickname to <username2>"
                    # String slicing to exclude common phrase and the fullstop
                    rawFoundNickname = regexResult.group(0)[self._PHRASE_OFFSET:-1]
                    foundNickname = self._fixMojibake(rawFoundNickname)
                    self._result.append({
                        'timestamp_ms': m['timestamp_ms'],
                        'nickname': foundNickname
                    })

        except Exception:
            print(f'Error: Bad JSON file {f}')

    def _isParticipant(self, participants: List[Dict[str, str]]) -> bool:
        # Check if `self.username` exists in the list `participants`
        # of the current conversation
        for p in participants:
            if p['name'] == self.username:
                return True
        return False

    def _fixMojibake(self, s: str) -> str:
        # Fix Facebook decoding error
        # Reference: https://stackoverflow.com/questions/50008296/facebook-json-badly-encoded
        return s.encode('latin1').decode('utf-8')

    def _unfixMojibake(self, s: str) -> str:
        # Undo _fixMojibake()
        return s.encode('utf-8').decode('latin1')


if __name__ == '__main__':
    parser = argparse.ArgumentParser('Python script listing all Facebook nicknames I\'ve had.')
    parser.add_argument('file', nargs='*', help='path to message JSONs, ignored if DIRECTORY is present')
    parser.add_argument('-d', '--directory', help='path to directory containing all the message JSONs')
    parser.add_argument('-u', '--username', help='your facebook username, used to skip checking your own messages')
    parser.add_argument('-o', '--output', default='output.json', help='result JSON file (default: output.json)')
    args = parser.parse_args()

    finder = FBNicknameFinder()
    finder.setUsername(args.username)

    if args.directory:
        finder.findInDirectory(args.directory)
    elif args.file:
        finder.findInFiles(args.file)
    else:
        parser.print_help()
        import sys
        sys.exit(0)

    if not finder.crashed:
        finder.printResult()
        finder.writeResult(args.output)
        print(f'Output written to {args.output}')
