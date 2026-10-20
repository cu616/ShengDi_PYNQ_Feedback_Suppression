"""一条命令对齐：给刚拉完代码的 AI（或人）30 秒内看清全部上下文。

    python scripts/brief.py            # 全部
    python scripts/brief.py --line b   # 只看我这条线相关的诉求

输出只有几行，因为它的价值在于"不用读十分钟"。信息来源全部是文件，不靠聊天记录：
  STATE.md 三条线的最后动作/当前卡点 → REQUESTS.md 的 open 行 → 各线日志最新一条 → 仓库状态
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINES = {'a': 'A 实物与板卡', 'b': 'B 数据与算法', 'c': 'C 测评与工具'}


LINK = re.compile(r'\[([^\]]*)\]\([^)]*\)')


def plain(text):
    """终端里把 markdown 链接显示成纯文字，别让 [R-001](REQUESTS.md) 刷屏。"""
    return LINK.sub(r'\1', text)


def read(path):
    try:
        return (ROOT / path).read_text(encoding='utf-8')
    except OSError:
        return ''


def git(*args):
    try:
        out = subprocess.run(('git',) + args, cwd=ROOT, capture_output=True, text=True)
        return out.stdout.strip() if out.returncode == 0 else ''
    except OSError:
        return ''


def state_lines():
    """抓 STATE.md 里三条线的两行摘要。"""
    text = read('docs/STATE.md')
    out = []
    for key, title in LINES.items():
        start = text.find('### ' + title[:1] + ' ')
        if start < 0:
            out.append((title, '（STATE.md 里找不到这一段）', ''))
            continue
        chunk = text[start:start + 500]
        action = re.search(r'\*\*最后动作\*\*[：:]\s*(.+)', chunk)
        block = re.search(r'\*\*当前卡点\*\*[：:]\s*(.+)', chunk)
        out.append((title,
                    plain(action.group(1).strip()) if action else '（缺"最后动作"行）',
                    plain(block.group(1).strip()) if block else ''))
    return out


def open_requests(line=None):
    """返回 REQUESTS.md 里 open 的行（按"到"过滤）。"""
    text = read('docs/REQUESTS.md')
    rows = []
    for raw in text.splitlines():
        if not raw.startswith('|') or '| open |' not in raw:
            continue
        cells = [cell.strip() for cell in raw.strip().strip('|').split('|')]
        if len(cells) < 6:
            continue
        rid, who, what, blocks = cells[0], cells[1], cells[2], cells[3]
        target = who.split('→')[-1].strip().lower() if '→' in who else ''
        if line and target != line:
            continue
        rows.append((rid, who, what, blocks))
    return rows


def latest_logs():
    """每条线日志最新的一条标题；没有分线日志时退回 progress.md。"""
    found = []
    for key in ('a', 'b', 'c'):
        text = read('docs/log/progress-%s.md' % key)
        for raw in text.splitlines():
            if raw.startswith('## '):
                found.append((key.upper(), raw[3:].strip()))
                break
    if found:
        return found
    text = read('docs/log/progress.md')
    heads = [line[3:].strip() for line in text.splitlines() if line.startswith('## ')]
    return [('LOG', head) for head in heads[:3]]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--line', choices=('a', 'b', 'c'), default=None,
                        help='只显示到这条线的诉求')
    args = parser.parse_args(argv)

    head = git('log', '-1', '--format=%h %s')
    dirty = len([line for line in git('status', '--porcelain').splitlines() if line])
    branch = git('branch', '--show-current') or '?'

    print('== 声堤 · 30 秒对齐 ==')
    print('分支 %s @ %s %s' % (branch, head or '（无提交）',
                               '· %d 项未提交改动' % dirty if dirty else '· 工作区干净'))

    print('\n【三条线到哪了】')
    for title, action, block in state_lines():
        print('  %-12s %s' % (title, action))
        if block:
            print('  %-12s ↳ %s' % ('', block))

    rows = open_requests(args.line)
    print('\n【要你做的事】%s' % ('（到 = %s）' % args.line.upper() if args.line else ''))
    if not rows:
        print('  没有指向你的未完成诉求。')
    for rid, who, what, blocks in rows:
        print('  %s %s' % (rid, who))
        print('      要：%s' % plain(what)[:110])
        print('      挡：%s' % plain(blocks)[:110])

    print('\n【最近日志】')
    for tag, head_line in latest_logs():
        print('  [%s] %s' % (tag, head_line))

    print('\n【下一步】')
    print('  1) 读 docs/lines/%s-*.md 确认自己的职责与文件边界' % (args.line or '<你的线>'))
    print('  2) 改完按 AGENTS.md 收工六步：改 STATE 两行 → 追加日志 → 关诉求 → 放证据 → 给提交信息')
    print('  3) 提交前跑：python scripts/check_docs.py')
    return 0


if __name__ == '__main__':
    sys.exit(main())
