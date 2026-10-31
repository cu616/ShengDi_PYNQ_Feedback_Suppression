import pathlib
p = pathlib.Path(r"D:\OCadence_Project\Flushbonading_FPGA_Contest\_a_work\wt-a\board\audio_replay\deliver_check.py")
t = p.read_text(encoding="utf-8")
t = t.replace("REPO = ROOT.parents[2]                       # board/audio_replay -> repo root\nWORK = REPO / '_a_work'",
              "WORK = ROOT.parents[2]                       # .../_a_work\nREPO = ROOT.parents[3]                       # .../Flushbonading_FPGA_Contest")
p.write_text(t, encoding="utf-8", newline="\n")
print("paths fixed")