#!/usr/bin/env python3
"""Run a design discussion from the command line.

This script demonstrates how to use the DiscussionCrew to run
multi-agent design discussions.

Usage:
    python scripts/run_discussion.py --topic "设计一个背包系统" --rounds 2
    python scripts/run_discussion.py -t "角色成长系统设计" -r 3
"""

import argparse
import sys
from pathlib import Path

# Add the parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.crew.discussion_crew import DiscussionCrew
from src.monitoring.langfuse_client import flush_langfuse, init_langfuse


def print_header(text: str) -> None:
    """Print a formatted header."""
    width = 60
    print()
    print("=" * width)
    print(f"  {text}")
    print("=" * width)
    print()


def print_agent_info(crew: DiscussionCrew) -> None:
    """Print information about the participating agents."""
    print_header("参与讨论的 Agent")
    for agent in crew.agents:
        print(f"  * {agent.role}")
        print(f"    目标: {agent.goal[:50]}...")
        print()


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="运行 AI 策划团队讨论",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
    python scripts/run_discussion.py --topic "设计一个背包系统"
    python scripts/run_discussion.py --topic "角色成长系统" --rounds 2
    python scripts/run_discussion.py -t "战斗系统设计" -r 3 --verbose
        """,
    )
    parser.add_argument(
        "-t",
        "--topic",
        required=True,
        help="讨论话题 (必填)",
    )
    parser.add_argument(
        "-r",
        "--rounds",
        type=int,
        default=2,
        help="讨论轮数 (默认: 2)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="显示详细输出",
    )
    parser.add_argument(
        "--no-trace",
        action="store_true",
        help="禁用 Langfuse 追踪",
    )

    args = parser.parse_args()

    # Initialize Langfuse if not disabled
    if not args.no_trace:
        init_langfuse()

    print_header(f"AI 策划团队讨论: {args.topic}")

    print(f"话题: {args.topic}")
    print(f"轮数: {args.rounds}")
    print()

    # Create the crew
    crew = DiscussionCrew()
    print_agent_info(crew)

    print_header("讨论开始")

    try:
        # Run the discussion
        result = crew.run(
            topic=args.topic,
            rounds=args.rounds,
            verbose=args.verbose,
        )

        print_header("讨论结果")
        print(result)
        print()

        # Flush any pending Langfuse events
        if not args.no_trace:
            flush_langfuse()

        print_header("讨论完成")
        return 0

    except KeyboardInterrupt:
        print("\n\n讨论被用户中断")
        return 130

    except Exception as e:
        print(f"\n错误: {e}")
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
