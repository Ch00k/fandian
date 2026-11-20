"""The `fand` command."""

import argparse
import pydoc
import sys

from . import charter, persona, target
from .api import ApiError, Unreachable
from .claude import PlanError
from .header import HeaderError
from .instance import InstanceError
from .run import run
from .target import TargetError

_EXAMPLES = """\
examples:
  fand run ~/projects/example newcomer                    a session of the newcomer persona
  fand run https://github.com/owner/example newcomer      the same, from the repository
  fand run ~/projects/example newcomer --check            start the instance, print the wiring, stop
  fand run ~/projects/example newcomer --charter          show the newcomer's charter
"""


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="fand", epilog=_EXAMPLES, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", metavar="command")
    p_run = sub.add_parser("run", help="test a fresh instance of a target as one persona")
    p_run.add_argument(
        "target", help="a checkout with a .fandian/ directory, or its repository's URL to clone"
    )
    p_run.add_argument("persona", help="a persona in personas/ or the target's .fandian/personas/")
    p_run.add_argument("--focus", metavar="focus", help="test only this feature (.fandian/focus/)")
    only = p_run.add_mutually_exclusive_group()
    only.add_argument(
        "--check",
        action="store_true",
        help="start the instance, print the resolved wiring and stop, without starting Claude",
    )
    only.add_argument(
        "--charter",
        action="store_true",
        help="show the charter the tester would be given, in a pager, and stop",
    )
    args = parser.parse_args()

    if args.command != "run":
        parser.print_help(sys.stderr)
        sys.exit(2)

    try:
        chosen = target.load(args.target)
        tester = persona.load(chosen, args.persona)
        if args.focus is not None:
            target.check_focus(chosen, args.focus, tester.name)
        if args.charter:
            pydoc.pager(charter.compose(chosen, tester, args.focus))
        else:
            run(chosen, tester, focus=args.focus, check=args.check)
    except (ApiError, Unreachable, PlanError, HeaderError, InstanceError, TargetError) as e:
        sys.exit(str(e))
    except KeyboardInterrupt:
        sys.exit("\nStopped.")


if __name__ == "__main__":
    main()
