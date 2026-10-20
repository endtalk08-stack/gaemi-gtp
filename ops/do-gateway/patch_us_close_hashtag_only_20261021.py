"""Single exact, authorized prod prompt edit; no other source changes."""
import ast
import os
import stat
import tempfile
from pathlib import Path

p=Path("/opt/gaemigtp-news/app/backend/services/us_market_close.py")
before=p.read_text(encoding="utf-8")
before_ast=ast.parse(before)
def prompt_of(tree):
    matches=[n for n in tree.body if isinstance(n,ast.Assign) and
             any(isinstance(t,ast.Name) and t.id=="US_CLOSE_PROMPT" for t in n.targets)]
    if len(matches)!=1:
        raise RuntimeError("prompt_definition_count_mismatch")
    return ast.literal_eval(matches[0].value)
old_prompt=prompt_of(before_ast)
old_token='"tags":["#핵심어"],"source_ids":[1]'
new_token='"tags":["#해시태그"],"source_ids":[1]'
if old_prompt.count(old_token)!=1 or before.count(old_token)!=1:
    raise RuntimeError("unexpected_old_prompt_aborting_without_changes")
if old_prompt.count('"source_ids":[1]')!=1:
    raise RuntimeError("unexpected_source_ids_aborting_without_changes")
after=before.replace(old_token,new_token,1)
new_prompt=prompt_of(ast.parse(after))
if new_prompt!=old_prompt.replace(old_token,new_token,1):
    raise RuntimeError("nonprompt_change_aborting")
if after.replace(new_token,old_token,1)!=before:
    raise RuntimeError("unexpected_file_diff_aborting")
original_stat=p.stat()
tmpname=None
try:
    fd,tmpname=tempfile.mkstemp(prefix=".us-close-hashtag-",dir=str(p.parent))
    with os.fdopen(fd,"w",encoding="utf-8") as stream:
        stream.write(after)
        stream.flush()
        os.fsync(stream.fileno())
    os.chmod(tmpname,stat.S_IMODE(original_stat.st_mode))
    if os.geteuid()==0:
        os.chown(tmpname,original_stat.st_uid,original_stat.st_gid)
    # Detect concurrent edits prior to atomic replace.
    if p.read_text(encoding="utf-8")!=before:
        raise RuntimeError("source_changed_concurrently_aborting")
    os.replace(tmpname,p)
    tmpname=None
finally:
    if tmpname and os.path.exists(tmpname):
        os.unlink(tmpname)
actual=p.read_text(encoding="utf-8")
if actual!=after or prompt_of(ast.parse(actual))!=new_prompt:
    raise RuntimeError("written_prompt_mismatch")
print("OPERATING_US_CLOSE_PROMPT_EXACT_EDIT=SUCCESS",flush=True)
print("ONLY_CHANGE",old_token,"=>",new_token,flush=True)
print("SOURCE_IDS_RETAINED",'"source_ids":[1]' in new_prompt,flush=True)
print("PROMPT_VERBATIM_START",flush=True)
print(new_prompt,flush=True)
print("PROMPT_VERBATIM_END",flush=True)
