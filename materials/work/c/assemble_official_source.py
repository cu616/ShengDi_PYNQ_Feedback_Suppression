"""Assemble the reviewable outer engineering archive, preserving frozen ZIP bytes."""
import argparse
import csv
import difflib
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile
import tempfile
import zipfile

from verify_official_source import verify, ZIP_NAME, ZIP_SHA, MANIFEST_SHA, BIT_SHA, digest

ROOT = Path(__file__).resolve().parents[3]
SNAPSHOT = 'faab2732fea5ebac44bb81ecc7d6b745e95dfd7e'
RUNTIME = '4efd43036555c667924fc415d31cf95d785fbb24'
FPGA = '31882e090e816ed69918d9b3fb4bec2910edaf62'
SOURCE_MAP = 'report/verification/recal-product-v1/resume3-source-map.json'
PACKAGE = 'report/verification/recal-product-v1/packages/' + ZIP_NAME
IMPLEMENTATION = 'report/verification/recal-product-v1/frozen-bitstream-32235065/'
HISTORICAL = {
    'recal_product.py': ('4efd43036555c667924fc415d31cf95d785fbb24', 'board/audio_replay/recal_product.py'),
    'hw_api.py': ('0d349af6b6984c299cc04da1d57f90921a836b7f', 'board/audio_replay/hw_api.py'),
    'recal_link.py': ('de775e19bfdd05d544b2d915af7dce3094bf6cd5', 'board/audio_replay/recal_link.py'),
    'replay_trial_repair.py': ('5939ee5b02b9d14dcf7fde076967f896f2cd9814', 'board/audio_replay/v3-io/replay_trial_repair.py'),
}
PRIVATE_EXTENSIONS = {'.wav', '.mp3', '.flac', '.m4a', '.aac', '.npz', '.npy', '.pcm', '.mp4', '.mov', '.mkv'}
ARCHIVE_EXTENSIONS = {'.zip', '.rar', '.7z'}


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, stderr=subprocess.PIPE)


def blob(commit, path):
    return git('show', commit + ':' + path)


def json_bytes(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def archive_files(commit, *paths):
    with tarfile.open(fileobj=io.BytesIO(git('archive', '--format=tar', commit, *paths))) as tar:
        for member in tar:
            if member.isfile():
                yield member.name, tar.extractfile(member).read()


def redact_record(data):
    """Publish an explicitly labelled privacy copy; frozen payload never calls this."""
    encoding = ('utf-16' if data[:2] in (b'\xff\xfe', b'\xfe\xff') else
                'utf-8-sig' if data.startswith(b'\xef\xbb\xbf') else 'utf-8')
    try:
        text = data.decode(encoding)
    except UnicodeDecodeError:
        encoding = 'gb18030'
        text = data.decode(encoding)
    rules = [
        (r'(?i)[A-Z]:[\\/]+Users[\\/]+[^\\/\s"\x27<>]+', '<user-home>'),
        (r'(?i)\b(?:LAPTOP|DESKTOP)-[A-Z0-9-]+', '<host>'),
        (r'\b(?:10|127|192\.168|172\.(?:1[6-9]|2\d|3[01]))(?:\.\d{1,3}){2,3}\b', '<local-ip>'),
        (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b', '<email>'),
    ]
    count = 0
    for pattern, replacement in rules:
        text, n = re.subn(pattern, replacement, text)
        count += n
    return (text.encode(encoding) if count else data), count


def redact_implementation(data):
    """Only host/user/machine-specific path fields; preserve dates, warnings and numbers."""
    text = data.decode('utf-8-sig')
    rules = [
        (r'(?i)[A-Z]:[\\/]+Users[\\/]+[^\\/\s"\x27<>]+', '<user-home>'),
        (r'(?i)\b(?:LAPTOP|DESKTOP)-[A-Z0-9-]+', '<host>'),
        (r'(?i)[A-Z]:[\\/]+[^\r\n"|]*?(?=(?:_a_work|build|src|sim|report)[\\/])', '<project>/'),
    ]
    count = 0
    for pattern, replacement in rules:
        text, n = re.subn(pattern, replacement, text)
        count += n
    return (text.encode('utf-8-sig' if data.startswith(b'\xef\xbb\xbf') else 'utf-8') if count else data), count


def assemble(args):
    snapshot = git('rev-parse', args.snapshot).decode().strip()
    work = Path(tempfile.mkdtemp(prefix='official-source-', dir=ROOT / 'tmp')).resolve()
    work.relative_to((ROOT / 'tmp').resolve())
    package_root = work / 'shengdi-source'
    records, excluded = {}, []

    def put(path, data, source, role, **extra):
        name = PurePosixPath(path)
        if name.is_absolute() or '..' in name.parts:
            raise ValueError('unsafe output path: ' + path)
        target = package_root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and target.read_bytes() != data:
            raise ValueError('would overwrite a different included file: ' + path)
        target.write_bytes(data)
        records[path] = dict(sha256=digest(data), bytes=len(data), source=source, role=role, **extra)

    # Source/verification helpers at the original frozen release source commit.
    for path, data in archive_files(RUNTIME, 'src', 'sim', 'scripts', 'models', 'build/scripts', 'data'):
        if Path(path).suffix.lower() in PRIVATE_EXTENSIONS | ARCHIVE_EXTENSIONS:
            excluded.append(dict(path=path, source=RUNTIME, reason='raw media/data or redundant archive'))
            continue
        put(path, data, RUNTIME + ':' + path, 'reproduction-source-or-test')
    # Support mock stays outside the exact 41-file runtime directory.
    put('sim/support/recal_mock.py', blob(RUNTIME, 'board/audio_replay/recal_mock.py'),
        RUNTIME + ':board/audio_replay/recal_mock.py', 'software-test-support-only')

    # Existing evidence, skills and current design report. Never publish returned PCM archives.
    for path, data in archive_files(snapshot, 'report', 'skill'):
        if path.startswith(IMPLEMENTATION):
            continue  # handled below with original/delivery hashes and explicit DCP exclusion
        ext = Path(path).suffix.lower()
        if ext in PRIVATE_EXTENSIONS | ARCHIVE_EXTENSIONS or (ext in {'.txt', '.log'} and len(data) > 300000):
            excluded.append(dict(path=path, source=snapshot, reason='private/raw data, repeated archive or long regenerable log'))
            continue
        destination = path
        role = 'historical-or-development-evidence-not-implementation-binding'
        if '/capture-plan-' in path:
            destination = 'development/main/' + path
            role = 'later-development-evidence-not-deployed'
        elif path.startswith('skill/'):
            role = 'reusable-skill'
        original_hash = digest(data)
        redactions = 0
        if path.startswith('report/') and ext in {'.md', '.txt', '.json'}:
            data, redactions = redact_record(data)
        put(destination, data, snapshot + ':' + path, role,
            original_sha256=original_hash, privacy_redactions=redactions)
    for name in ['shengdi-technical-report-review.docx', 'shengdi-technical-report-review.pdf']:
        path = 'materials/final/' + name
        put('report/design/' + name, blob(snapshot, path), snapshot + ':' + path, 'existing-review-report-not-approved-final')

    # Later code is readable development history, isolated from the deployed 41 files.
    development = [
        'board/audio_replay/recal_product.py', 'board/audio_replay/hw_api.py',
        'board/audio_replay/recal_link.py', 'board/audio_replay/v3-io/replay_trial_repair.py',
        'sim/feedback/test_recal_capture_plan.py', 'scripts/diag_highfreq_phase.py',
        'sim/feedback/test_highfreq_phase_audit.py', 'docs/STATE.md',
    ]
    for path in development:
        put('development/main/' + path, blob(snapshot, path), snapshot + ':' + path,
            'later-development-not-deployed')

    frozen_zip = blob(snapshot, PACKAGE)
    if digest(frozen_zip) != ZIP_SHA:
        raise ValueError('captain ZIP pin differs')
    source_map = json.loads(blob(snapshot, SOURCE_MAP))
    put('board/packages/' + ZIP_NAME, frozen_zip, snapshot + ':' + PACKAGE, 'immutable-deployment-attachment')
    for suffix in ['json', 'md']:
        path = SOURCE_MAP.rsplit('.', 1)[0] + '.' + suffix
        put('board/provenance/resume3-source-map.' + suffix, blob(snapshot, path), snapshot + ':' + path, 'captain-original-source-map')
    rows, differences, patch = [], [], []
    with zipfile.ZipFile(io.BytesIO(frozen_zip)) as zipped:
        for item in source_map['files']:
            name = item['file']
            data = zipped.read(name)
            if digest(data) != item['sha256'] or len(data) != item['bytes']:
                raise ValueError('frozen source map differs: ' + name)
            repo_path = item.get('repo_source') or item.get('repo_path')
            origin, original_match = '仅包内，由C组装', None
            if name in HISTORICAL:
                commit, repo_path = HISTORICAL[name]
                original_match = blob(commit, repo_path) == data
                if not original_match:
                    raise ValueError('historical source differs: ' + name)
                origin = commit + ':' + repo_path
            elif item.get('provenance') == 'repo-same-content' and repo_path:
                original_match = blob(snapshot, repo_path) == data
                if original_match:
                    origin = snapshot + ':' + repo_path
            role = ('deployment-operations-document' if Path(name).suffix.lower() == '.md'
                    else 'frozen-runtime-configuration-or-payload')
            put('board/audio_replay/' + name, data, 'ZIP:' + ZIP_NAME + ':' + name, role,
                source_reference=origin, repo_path=repo_path, historical_bytes_match=original_match)
            rows.append(dict(file=name, archive_path='board/audio_replay/' + name,
                             sha256=digest(data), bytes=len(data), repo_path=repo_path,
                             source=origin, source_map_category=item['provenance'], role=role))
            diff = dict(file=name, frozen_sha256=digest(data), repo_path=repo_path)
            if origin == '仅包内，由C组装':
                diff['comparison'] = 'package-only-or-no-exact-Git-blob; never regenerate'
            if repo_path:
                try:
                    current = blob(snapshot, repo_path)
                    diff.update(main_sha256=digest(current), same_bytes=current == data)
                    if current != data:
                        diff['comparison'] = ('line-ending-only' if current.replace(b'\r\n', b'\n') == data.replace(b'\r\n', b'\n') else 'content-differs')
                        if Path(name).suffix == '.py':
                            patch.extend(difflib.unified_diff(data.decode().splitlines(True), current.decode().splitlines(True),
                                         fromfile='frozen/' + name, tofile='main/' + repo_path))
                    else:
                        diff['comparison'] = 'same-bytes-at-pinned-main-snapshot'
                except subprocess.CalledProcessError:
                    diff['comparison'] = 'package-only; no tracked main path'
            else:
                diff.setdefault('comparison', 'package-only; no repository source')
            differences.append(diff)
    put('board/provenance/frozen-file-sources.json', json_bytes(rows), 'C outer assembly', '41-file-origin-index')
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader();writer.writerows(rows)
    put('board/provenance/frozen-file-sources.csv', stream.getvalue().encode('utf-8-sig'), 'C outer assembly', '41-file-origin-index')
    put('board/provenance/frozen-vs-main.json', json_bytes(dict(main_snapshot=snapshot, files=differences)), 'C byte comparison', 'development-difference-index')
    put('board/provenance/frozen-vs-main.patch', ''.join(patch).encode(), 'C text comparison; frozen inputs unchanged', 'development-difference-view')
    cli = subprocess.run([sys.executable, '-B', '-X', 'utf8',
        str(package_root / 'board/audio_replay/recal_product.py'), '--base',
        str(package_root / 'board/audio_replay'), '--check'], check=True,
        capture_output=True, text=True, encoding='utf-8')
    cli_check = json.loads(cli.stdout)
    if cli_check != dict(identity_ok=True, deployment_ready=True, missing=[]):
        raise ValueError('frozen CLI check differs: ' + cli.stdout)
    frozen_check = dict(zip_sha256=ZIP_SHA, product_manifest_sha256=MANIFEST_SHA,
        bit_sha256=BIT_SHA, file_count=41, all_files_match_source_map=True,
        all_extracted_bytes_match_original_zip=True, historical_four_match=True,
        cli_check=cli_check, cli_exit=cli.returncode, files=rows, hardware_operations=0)
    put('report/submission/frozen-payload-check.json', json_bytes(frozen_check),
        'C original ZIP/Git/CLI audit; no hardware', 'frozen-payload-verification')

    # Original implementation evidence, supplied by A and explicitly approved by captain.
    sums_bytes = blob(snapshot, IMPLEMENTATION + 'sha256sums.txt')
    listed, checked, unavailable, delivery_copies = [], [], [], []
    for line in sums_bytes.decode('utf-8-sig').splitlines():
        if not line.strip():
            continue
        expected, name = line.split(None, 1)
        name = name.strip()
        listed.append(dict(file=name, sha256=expected))
        try:
            data = blob(snapshot, IMPLEMENTATION + name)
        except subprocess.CalledProcessError:
            unavailable.append(dict(file=name, sha256=expected,
                reason='listed by A, not present in supplied Git commit; reference only, not locally verified'))
            continue
        git_blob_sha256 = digest(data)
        materialization = 'exact Git blob'
        if digest(data) != expected:
            # Some original Vivado reports were committed with text normalization.
            # Restore a known original only if its approved full SHA256 matches.
            if Path(name).suffix.lower() not in {'.rpt', '.txt', '.log'}:
                raise ValueError('original implementation hash differs: ' + name)
            normalized = data.replace(b'\r\n', b'\n')
            variants = [normalized, normalized.replace(b'\n', b'\r\n')]
            matching = [v for v in variants if digest(v) == expected]
            if not matching:
                raise ValueError('original implementation hash differs: ' + name)
            data = matching[0]
            materialization = 'Git text-normalized EOL restored; approved original SHA256 exact'
        checked.append(dict(file=name, sha256=expected, git_blob_sha256=git_blob_sha256,
                            source_materialization=materialization))
        if name.endswith('.dcp'):
            excluded.append(dict(path=IMPLEMENTATION + name, source=snapshot, sha256=expected,
                reason='captain: DCP retained in repository, excluded from RAR'))
            continue
        published, replacements = redact_implementation(data)
        destination = IMPLEMENTATION + name
        put(destination, published, snapshot + ':' + destination, 'frozen-bit-implementation-report',
            original_sha256=expected, privacy_redactions=replacements,
            git_blob_sha256=git_blob_sha256, source_materialization=materialization,
            transformation='only host/user/machine-path redaction; technical fields unchanged')
        delivery_copies.append(dict(file=name, original_sha256=expected, delivery_sha256=digest(published),
            git_blob_sha256=git_blob_sha256, source_materialization=materialization,
            privacy_redactions=replacements, rules=['Windows user-home prefix', 'host name',
                'machine absolute project prefix; project-relative suffix retained']))
    source_path = IMPLEMENTATION + 'build-provenance.md'
    original = blob(snapshot, source_path)
    published, replacements = redact_implementation(original)
    scope_note = '''

---
## 交付副本范围说明（C按队长2026-11-03修订口径附注）

本说明中的DCP为仓库留存证据，不随RAR分发；上文相对DCP链接不是本包文件。
仓库位置：report/verification/recal-product-v1/frozen-bitstream-32235065/dcp/system_wrapper_routed.dcp。
其SHA256与原件清单一致；取得仓库时按该提交查看，勿将本包缺少DCP误当作空文件。
原件清单中的logs/runme.log未包含在本次提供的Git提交中；其哈希保留为来源引用，C未宣称独立核验该日志。

本包对外采用：已施加的时序约束全部满足；DRC无Error。保留时钟定义与部分I/O延迟约束告警。
原记录中的解释性判断不扩展本包保证；不据此宣称所有接口时序均已验证。
sha256sums.txt是A原件清单（含未分发DCP与引用日志），不得用于验证已脱敏副本。
本包副本请核对delivery-sha256sums.txt与implementation-report-copies.json。
'''
    published += scope_note.encode()
    put(source_path, published, snapshot + ':' + source_path, 'frozen-bit-build-provenance-with-delivery-scope-note',
        original_sha256=digest(original), privacy_redactions=replacements,
        annotations='appended scope note identifies repository-only DCP, unavailable log, approved warning wording')
    delivery_copies.append(dict(file='build-provenance.md', original_sha256=digest(original),
        delivery_sha256=digest(published), privacy_redactions=replacements,
        rules=['host/user/machine-path redaction', 'explicit appended delivery scope note']))
    put(IMPLEMENTATION + 'sha256sums.txt', sums_bytes, snapshot + ':' + IMPLEMENTATION + 'sha256sums.txt',
        'original-source-checksums-not-delivery-copy-checksums')
    delivery_sums = ''.join(x['delivery_sha256'] + '  ' + x['file'] + '\n' for x in delivery_copies)
    put(IMPLEMENTATION + 'delivery-sha256sums.txt', delivery_sums.encode(), 'C delivery-copy audit', 'delivery-copy-checksums')
    implementation_check = dict(source_commit=snapshot, bit_sha256=BIT_SHA,
        listed_originals=len(listed), checked_originals=checked, unavailable_originals=unavailable,
        dcp_in_archive=False, copies=delivery_copies,
        report_stage_labels_retained=True, resynthesized=False,
        wording='已施加的时序约束全部满足；DRC无Error。保留时钟定义与部分I/O延迟约束告警。',
        resources=dict(lut=3587, ff=5030, bram_used=112, bram_available=140, dsp=3),
        timing_ns=dict(wns=0.735, whs=0.032),
        report_origin='original 2026-11-01 build plus separately labelled 2026-11-03 routed-utilization re-export')
    put(IMPLEMENTATION + 'implementation-report-copies.json', json_bytes(implementation_check),
        'C original/delivery hash audit; captain-approved source faab273', 'implementation-evidence-audit')

    # Verify the FPGA dependency closure against the commit introducing the exact bit.
    fpga_paths = ['src/rtl/audio_pl_replay.v', 'src/rtl/feedback_fir.v',
                  'src/vendor/pynq_v2_4/iis_ser.vhd', 'src/vendor/pynq_v2_4/iis_deser.vhd',
                  'build/scripts/create_audio_replay_io.tcl', 'build/scripts/audio_replay_io.xdc']
    fpga_sources = []
    for path in fpga_paths:
        data = blob(FPGA, path)
        if (package_root / path).read_bytes() != data:
            raise ValueError('FPGA introduction source differs: ' + path)
        fpga_sources.append(dict(path=path, sha256=digest(data), source=FPGA + ':' + path))
    put('build/frozen-bit-source-audit.json', json_bytes(dict(bit_sha256=BIT_SHA,
        bit_introduction_commit=FPGA, source_files=fpga_sources,
        source_relation='same bytes at bit-introduction commit; A original-build provenance supplied in faab273',
        implementation_evidence=IMPLEMENTATION + 'implementation-report-copies.json',
        matching_implementation_reports_available=True, rebuilt=False)), 'C static Git/source-report audit', 'build-provenance')

    missing = [
        dict(id='final-design-report', state='pending-confirmation', detail='只收录现有review同稿DOCX/PDF；内含待补实拍图及历史待验证措辞，未获终稿确认。'),
        dict(id='environment-lock', state='incomplete', detail='Vivado2018.3/PYNQ-Z2 board_part已由Tcl固定；板上Python/NumPy/PYNQ精确版本和外部board_part定义未随冻结包完整锁定。'),
    ]
    put('report/submission/missing-items.json', json_bytes(missing), 'C package review', 'declared-incomplete-items')
    put('report/submission/excluded-files.json', json_bytes(excluded), 'C inclusion policy', 'exclusion-index')

    readme = f'''# 声堤完整工程候选（待缺项关闭）

唯一部署身份：release beb36216d26b6cbb，ZIP `{ZIP_SHA}`，product-manifest `{MANIFEST_SHA}`。
这是可检查候选，尚非最终上传批准。缺项见 report/submission/missing-items.json；不以旧报告或空文件补齐。

## 目录与复现

| 指南目录 | 本包位置及用途 |
|---|---|
| src | RTL、Python参考实现、PYNQ VHDL与原BSD许可；来源RUNTIME={RUNTIME} |
| sim | 既有仿真/软件验证源；sim/support仅为模拟辅助，不属于部署41文件 |
| build | 可复现Tcl/XDC；正式I/O入口为build/scripts/create_audio_replay_io.tcl |
| board | audio_replay为原ZIP原样解压的41文件；packages为原ZIP；provenance为外部来源/差异表 |
| data / models | 非私人数据说明及既有模型/参考；不包含私人PCM或返回录音包 |
| skill | main快照{snapshot}的技能包、引用与失效边界 |
| report | 同稿设计报告、验证证据及协作纠错记录；所有旧版/开发结果保留其原范围 |
| scripts / tools | 兼容既有测试工具及本次外层打包/核验工具 |
| development | main后续批量/诊断代码，非正式运行入口，禁止覆盖board/audio_replay |

冻结源码一律不要注释、格式化、改行尾或改名。OPERATIONS.md等为部署/运维文档，不计作程序源码。
来源表中“仅包内，由C组装”的文件仅从ZIP取得；source-map中空commit字段不构成可用历史来源。
source-map.md中的PowerShell重定向示例不用于本次取件；所有字节由ZIP或git原始输出读取。

1. 解压后在本目录执行 `python tools/submission/verify_official_source.py .`，要求ok=true、frozen_files=41。
2. 板卡部署只按board/audio_replay/OPERATIONS.md及product-install.sh执行，由A独占板卡。
   包内配置4596/+1dB、60秒、4训练2验证、runtime白名单不重建、不修改。
3. 仅需重新生成FPGA工程时，依赖合法Vivado2018.3、xc7z020clg400-1及`tul.com.tw:pynq-z2:part0:1.0`。
   匹配入口命令为 `vivado -mode batch -source build/scripts/create_audio_replay_io.tcl -tclargs build`。
   本轮未执行此命令；构建对应关系的缺项必须先核实，不保证重新构建bit逐字节复现。
4. 单独复核软件测试需Python>=3.8、NumPy；将sim/support加入PYTHONPATH后使用sim/feedback下既有测试。
   软件通过不能代替声学/板上复现；包内源代码、模型、构建工具各自版本按清单解释。

## 必要边界

- `build/frozen-bit-source-audit.json`确认六项构建源码与位流首入库提交相同；对应实现报告为
  report/verification/recal-product-v1/frozen-bitstream-32235065/中的交付副本。
  已施加的时序约束全部满足；DRC无Error。保留时钟定义与部分I/O延迟约束告警。
  原始/补导出报告的日期与阶段分别保留；所有其他旧timing/utilization数字不能作为本位流结果。
  DCP留在仓库，不在RAR；来源说明中的原相对链接不是随包附件。原件SHA与副本SHA分别登记。
- report/design内是官网设计报告的现有review稿副本，无另写不同叙事；最终上传前需确认补图/措辞与实装一致。
- 补充文档/证据若包含个人Windows主目录、主机名、本地IP或邮箱，会收录明确标注的隐私副本；
  原始Git路径/提交与原SHA保存在submission-manifest。冻结ZIP与其41文件从不进入脱敏转换。
- 第三方源码只保留已有PYNQ v2.4 VHDL和原BSD-3-Clause LICENSE/来源。Vivado、PYNQ镜像、NumPy、
  board_part、厂商手册和赛事PDF均作为外部依赖/参考，不把未确认分发许可的PDF或工具安装包打入工程。
- 不含.git、账户凭证、私人录音、Vivado缓存/巨大中间工程、重复安装包和冗长仿真日志。
  仅保留指南需要的源码、脚本、参考/验证结果、技能与协作记录。排除项有逐文件清单。

## 外层清单

submission-manifest.json列出所有其他文件的SHA256/字节/逐文件来源，自身不自哈希；其SHA在外部交付回执。
原ZIP及解压41文件、四个历史源都已按外部source-map核验；main同名文件只用于差异表。
跨设备请发送shengdi-source.rar与.sha256文本作为原始文件；接收方先核SHA，再独立解压运行上面的核验。
RAR不随Git自动发布；Git只传小型打包工具、清单和回执。RAR工具通过官方RARLAB取得，不随包分发。
'''
    put('README.md', readme.encode(), 'C outer assembly instructions', 'submission-entry')
    for name in ['assemble_official_source.py', 'verify_official_source.py']:
        path = 'materials/work/c/' + name
        data = (Path(__file__).parent / name).read_bytes()
        origin = '仅包内，由C组装；packaging tool working source'
        try:
            commit = git('log', '-1', '--format=%H', '--', path).decode().strip()
            if commit and blob(commit, path) == data:
                origin = commit + ':' + path
        except subprocess.CalledProcessError:
            pass
        put('tools/submission/' + name, data, origin, 'outer-packaging-tool-not-runtime')
    put('tools/submission/README.txt', (
        'verify_official_source.py可在独立解压后直接运行。\n'
        'assemble_official_source.py仅在含完整Git历史的开发仓库materials/work/c下使用；不在发布解压目录重组冻结ZIP。\n'
        '需要RARLAB官方RAR命令；工具不随包分发。\n').encode(), 'C packaging notes', 'outer-tool-instructions')
    manifest = dict(candidate=True, upload_ready=False, snapshot=snapshot, runtime_source_commit=RUNTIME,
                    fpga_introduction_commit=FPGA, frozen_zip_sha256=ZIP_SHA, missing=missing,
                    self_hash_excluded=True, files=records)
    (package_root / 'submission-manifest.json').write_bytes(json_bytes(manifest))
    before = verify(package_root)
    rar = Path(args.rar).resolve()
    output = ROOT / 'materials/final/shengdi-source.rar'
    if output.exists():
        previous = output.with_name('shengdi-source.previous-' + digest(output.read_bytes())[:12] + '.rar')
        if not previous.exists():
            previous.write_bytes(output.read_bytes())
        # RAR update would retain removed files, so build to a new, non-existing path.
    temporary_archive = work / 'shengdi-source.rar'
    subprocess.run([str(rar), 'a', '-ma5', '-m4', '-s', '-ts-', '-idq', str(temporary_archive), 'shengdi-source'], cwd=work, check=True)
    if temporary_archive.stat().st_size >= 200000000:
        raise ValueError('RAR exceeds strict 200000000-byte limit')
    if temporary_archive.read_bytes()[:8] != b'Rar!\x1a\x07\x01\x00':
        raise ValueError('not an actual RAR5 archive')
    subprocess.run([str(rar), 't', '-idq', str(temporary_archive)], check=True)
    extracted = work / 'independent-extraction'
    extracted.mkdir()
    unrar = rar.with_name('UnRAR.exe')
    subprocess.run([str(unrar), 'x', '-idq', '-o-', str(temporary_archive), str(extracted) + '/'], check=True)
    after = verify(extracted / 'shengdi-source')
    if before != after:
        raise ValueError('independent extraction verification differs')
    output.write_bytes(temporary_archive.read_bytes())
    sidecar = output.with_suffix('.rar.sha256')
    sidecar.write_text(digest(output.read_bytes()) + '  ' + output.name + '\n', encoding='ascii')
    receipt = dict(candidate=True, upload_ready=False, archive_name=output.name, bytes=output.stat().st_size,
        sha256=digest(output.read_bytes()), magic='RAR5', rar_version='7.23',
        archive_test_exit=0, independent_extraction=after, frozen_check=before,
        snapshot=snapshot, runtime_source_commit=RUNTIME, fpga_introduction_commit=FPGA,
        staging_root=str(package_root), independently_extracted_root=str(extracted / 'shengdi-source'),
        final_path=str(output), source_files=len(records), frozen_files=41, hardware_operations=0,
        frozen_zip_regenerated=False, product_source_changed=False,
        frozen_cli_check=cli_check, frozen_cli_check_exit=cli.returncode,
        cross_device='Transfer the RAR and its .rar.sha256 as files; verify SHA256 then extract and run tools/submission/verify_official_source.py .')
    receipt_dir = ROOT / 'report/verification/recal-product-v1'
    (receipt_dir / 'official-source-candidate.json').write_bytes(json_bytes(receipt))
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--snapshot', default=SNAPSHOT)
    parser.add_argument('--rar', required=True)
    assemble(parser.parse_args())
