"""Run finite, hardware-free state tests in installed Bonsai (Python stdlib only).

python scripts/validate_detector.py --bonsai C:/Users/USER/AppData/Local/Bonsai/Bonsai.exe
Generated workflows and CSVs stay in scratch. Tests use the actual SongState.bonsai.
"""
import argparse
import csv
import subprocess
import time
from pathlib import Path
from xml.sax.saxutils import escape
from xml.dom.minidom import parseString


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bonsai', type=Path, required=True)
    parser.add_argument('--threshold', type=float, default=.01)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    folder = root / 'scratch' / ('state-tests-' + time.strftime('%Y%m%d-%H%M%S'))
    folder.mkdir(parents=True)
    exact = [int(i in list(range(0, 95, 5)) + [99]) for i in range(100)]
    below = [int(i in list(range(0, 90, 5)) + [99]) for i in range(100)]
    late = [int(i in list(range(0, 95, 5)) + [109,128] + list(range(137,145))) for i in range(145)]
    tests = {
        'silence': ([0]*300, []),
        'at-threshold': ([.5]*150+[0]*20, []),
        'blip': ([1]+[0]*200, [(20, 'rejected')]),
        'span-990ms': ([1]*99+[0]*20, [(118, 'rejected')]),
        'span-1000ms': ([1]*100+[0]*200, [(99, 'confirmed'), (119, 'completed')]),
        'gap-190ms': ([1]*100+[0]*19+[1]*100+[0]*20, [(99, 'confirmed'), (238, 'completed')]),
        'gap-200ms': ([1]*100+[0]*20+[1]*100+[0]*20, [(99, 'confirmed'), (119, 'completed'), (219, 'confirmed'), (239, 'completed')]),
        'gap-210ms': ([1]*100+[0]*21+[1]*100+[0]*20, [(99, 'confirmed'), (119, 'completed'), (220, 'confirmed'), (240, 'completed')]),
        'occupancy-20pct': (exact+[0]*20, [(99, 'confirmed'), (119, 'completed')]),
        'occupancy-19pct': (below+[0]*20, [(119, 'rejected')]),
        'occupancy-late-20pct': (late+[0]*20, [(144, 'confirmed'), (164, 'completed')]),
        'stop-mid-song': ([1]*110, [(99, 'confirmed')]),
        'stop-mid-candidate': ([1]*30, []),
        'reset-after-rejection': ([1]+[0]*20+[1]*100+[0]*20, [(20,'rejected'), (120,'confirmed'), (140,'completed')]),
        'exposed-span-and-quiet': ([1]*50+[0]*5, [(49,'confirmed'), (54,'completed')], {'MinSpanBlocks':50, 'QuietBlocks':5}),
        'exposed-occupancy': (exact+[0]*20, [(119,'rejected')], {'MinOccupancy':.5}),
        'exposed-threshold': ([1]*100+[0]*20, [(99,'confirmed'), (119,'completed')], {'Threshold':args.threshold/2}),
    }
    for name, case in tests.items():
        values, expected = case[:2]
        settings = dict(Threshold=args.threshold, MinSpanBlocks=100, MinOccupancy=.2, QuietBlocks=20)
        if len(case)>2:
            settings.update(case[2])
        output = folder / (name+'.csv')
        activity = ' : '.join(f'it == {i} ? {v*settings["Threshold"]*2:.8f}' for i,v in enumerate(values) if v) + ' : 0.0' if any(values) else '0.0'
        properties = ''.join(f'<{k}>{v}</{k}>' for k,v in settings.items())
        xml = f'''<WorkflowBuilder Version="2.9.1" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:rx="clr-namespace:Bonsai.Reactive;assembly=Bonsai.Core" xmlns:s="clr-namespace:Bonsai.Scripting.Expressions;assembly=Bonsai.Scripting.Expressions" xmlns:io="clr-namespace:Bonsai.IO;assembly=Bonsai.System" xmlns="https://bonsai-rx.org/2018/workflow">
<Workflow><Nodes>
<Expression xsi:type="Combinator"><Combinator xsi:type="rx:Range"><rx:Start>0</rx:Start><rx:Count>{len(values)}</rx:Count></Combinator></Expression>
<Expression xsi:type="s:ExpressionTransform"><s:Expression>{escape(activity)}</s:Expression></Expression>
<Expression xsi:type="IncludeWorkflow" Path="{(root/'bonsai/SongState.bonsai').as_posix()}">{properties}</Expression>
<Expression xsi:type="io:CsvWriter"><io:FileName>{output.as_posix()}</io:FileName><io:IncludeHeader>true</io:IncludeHeader></Expression>
</Nodes><Edges><Edge From="0" To="1" Label="Source1"/><Edge From="1" To="2" Label="Source1"/><Edge From="2" To="3" Label="Source1"/></Edges></Workflow></WorkflowBuilder>'''
        workflow = folder / (name+'.bonsai')
        workflow.write_text(parseString(xml).toprettyxml(indent='  '), encoding='utf-8')
        run = subprocess.run([str(args.bonsai), '--no-editor', str(workflow)], capture_output=True,
                             text=True, timeout=30, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        (folder/(name+'.log')).write_text(run.stdout+run.stderr)
        assert run.returncode == 0 and not run.stderr.strip(), (name, run.stderr)
        with output.open() as handle:
            rows = list(csv.DictReader(handle))
        assert len(rows) == len(values), (name, 'lost or duplicated blocks')
        assert [int(r['BlockIndex']) for r in rows] == list(range(len(values))), name
        actual = [(int(r['BlockIndex']), r['Event']) for r in rows if r['Event']]
        assert actual == expected, (name, actual, expected)
        print('PASS', name, flush=True)
    print(f'{len(tests)} native Bonsai tests passed. Evidence: {folder}')


if __name__ == '__main__':
    main()
