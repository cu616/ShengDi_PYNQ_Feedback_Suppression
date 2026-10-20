"""文档守门：断链、孤儿、重复的"现状"标题、契约状态头。

改完文档跑一次。这是唯一能防止文档体系在两周内退化的机制。

    python scripts/check_docs.py            # 报告并返回非零（有错误时）
    python scripts/check_docs.py --strict   # 警告也算失败

四条规则，对应 docs/WORKFLOW.md：
1. 相对链接必须能打开（改文件位置后最先烂的就是这个）。
2. docs/{lines,ref,rules,contracts,templates} 里的文件必须能被别的文档点到，
   否则它一定在腐烂而没人知道。
3. 除 STATE.md 外，不许再出现"当前状态/当前重点/当前接手点/现阶段"这类**标题**。
   这是之前乱掉的直接原因：同一件事有四个家。
4. 现行契约必须有"状态"行，否则别人无法判断它能不能被依赖。

另外检查 STATE.md 三条线是否都维护了"最后动作/当前卡点"两行。
"""
import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LINK = re.compile(r'(?<!\!)\[([^\]]*)\]\(([^)\s]+)')
RISKY_HEADING = re.compile(r'^\s{0,3}#{1,6}\s*.*(当前状态|当前重点|当前接手|目前状态|现阶段|下一步计划)')
# 只有这些位置允许出现"现状"式标题：它是权威，或它本身就是历史快照。
ALLOW_RISKY = ('STATE.md',)
CHECKED_DIRS = ('docs/lines', 'docs/ref', 'docs/rules', 'docs/contracts', 'docs/templates')
SKIP_ORPHAN = ('contracts/README.md',)


def md_files():
    for path in ROOT.rglob('*.md'):
        if '.git' in path.parts or 'tmp' in path.parts:
            continue
        yield path


def rel(path):
    return str(path.relative_to(ROOT)).replace('\\', '/')


def check_links(files):
    errors = []
    for path in files:
        text = path.read_text(encoding='utf-8')
        for match in LINK.finditer(text):
            target = match.group(2)
            if target.startswith(('http://', 'https://', 'mailto:', '#')):
                continue
            core = target.split('#')[0]
            if not core:
                continue
            if not (path.parent / core).exists():
                errors.append('%s: 断链 -> %s' % (rel(path), target))
    return errors


def check_orphans(files):
    inbound = {}
    for path in files:
        text = path.read_text(encoding='utf-8')
        for match in LINK.finditer(text):
            target = match.group(2)
            if target.startswith(('http', 'mailto:', '#')):
                continue
            core = target.split('#')[0]
            if not core:
                continue
            resolved = (path.parent / core).resolve()
            try:
                inbound[resolved] = inbound.get(resolved, 0) + 1
            except (OSError, ValueError):
                pass
    warnings = []
    for path in files:
        name = rel(path)
        if not name.startswith(CHECKED_DIRS):
            continue
        if any(name.endswith(skip) for skip in SKIP_ORPHAN):
            continue
        if inbound.get(path.resolve(), 0) == 0:
            warnings.append('%s: 零入链（没有任何文档指向它）' % name)
    return warnings


def check_risky_headings(files):
    warnings = []
    for path in files:
        name = rel(path)
        if any(name.endswith(a) for a in ALLOW_RISKY):
            continue
        if name.startswith(('docs/log/', 'docs/archive/', 'report/')):
            continue  # 时间线与证据允许保留当时的状态
        for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
            if RISKY_HEADING.match(line):
                warnings.append('%s:%d: 又在写"现状"标题 —— 应改为指向 docs/STATE.md'
                                % (name, number))
    return warnings


def check_contract_status(files):
    errors = []
    for path in files:
        name = rel(path)
        if not name.startswith('docs/contracts/') or name.startswith('docs/contracts/frozen/'):
            continue
        if name.endswith('README.md'):
            continue
        head = '\n'.join(path.read_text(encoding='utf-8').splitlines()[:10])
        if '状态' not in head:
            errors.append('%s: 缺"状态"行，别人无法判断能否依赖' % name)
    return errors


def check_state():
    """确认 STATE.md 三条线都有"最后动作/当前卡点"两行。

    这是"拉取后 30 秒对齐"的唯一支点：没有这两行，对方拉完还得读十分钟。
    注意：需要队友配合的事不进仓库，由人转发，所以这里不检查任何诉求表。
    """
    errors, warnings, info = [], [], []
    state = ROOT / 'docs/STATE.md'
    if not state.exists():
        return ['docs/STATE.md 不存在'], warnings, info
    body = state.read_text(encoding='utf-8')
    for line_name in ('### A ', '### B ', '### C '):
        start = body.find(line_name)
        if start < 0:
            warnings.append('docs/STATE.md: 找不到"%s"段' % line_name.strip())
            continue
        chunk = body[start:start + 400]
        for field in ('最后动作', '当前卡点'):
            if field not in chunk:
                warnings.append('docs/STATE.md: "%s"段缺"%s"行，拉取后无法 30 秒对齐'
                                % (line_name.strip(), field))
    return errors, warnings, info


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--strict', action='store_true', help='警告也视为失败')
    args = parser.parse_args(argv)

    files = sorted(md_files())
    errors = check_links(files) + check_contract_status(files)
    warnings = check_orphans(files) + check_risky_headings(files)
    state_errors, state_warnings, info = check_state()
    errors += state_errors
    warnings += state_warnings

    for line in errors:
        print('ERROR', line)
    for line in warnings:
        print('WARN ', line)
    for line in info:
        print('INFO ', line)
    print('\n扫描 %d 个 markdown 文件：%d 错误，%d 警告'
          % (len(files), len(errors), len(warnings)))
    if errors:
        return 1
    if warnings and args.strict:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
