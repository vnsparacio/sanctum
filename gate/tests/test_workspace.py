import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
BASE=Path(__file__).resolve().parents[1];sys.path[:0]=[str(BASE/'src')]
from common import Refused
from workspace import contained,create_worktree

class Workspace(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.repo=self.root/'repo';self.stage=self.root/'stage';self.repo.mkdir();self.stage.mkdir()
  subprocess.run(['/usr/bin/git','init','-q'],cwd=self.repo,check=True);(self.repo/'a.txt').write_text('synthetic\n')
  subprocess.run(['/usr/bin/git','add','a.txt'],cwd=self.repo,check=True);subprocess.run(['/usr/bin/git','-c','user.name=test','-c','user.email=test@example.invalid','commit','-qm','synthetic'],cwd=self.repo,check=True)
 def tearDown(self):self.tmp.cleanup()
 def test_owner_creates_clean_detached_worktree(self):
  result=create_worktree(str(self.repo),str(self.stage),'task-1');self.assertEqual(result['workspace_id'],'task-1');self.assertEqual(result['initial_status'],'');self.assertTrue((Path(result['root'])/'a.txt').is_file())
 def test_refuses_dirty_source_and_escape_names(self):
  (self.repo/'dirty').write_text('x')
  with self.assertRaises(Refused):create_worktree(str(self.repo),str(self.stage),'task-2')
  (self.repo/'dirty').unlink()
  for name in ('../outside','x/y',''):
   with self.assertRaises(Refused):create_worktree(str(self.repo),str(self.stage),name)
 def test_containment_has_no_parent_escape(self):
  self.assertTrue(contained(self.stage,self.stage/'new'));self.assertFalse(contained(self.stage,self.root/'other'))
