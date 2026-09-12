import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'router'))
from escalation import TrustedContext,decide,dispatch
class Escalation(unittest.TestCase):
 def test_local_success(self):self.assertEqual(decide(TrustedContext())['final_outcome'],'LOCAL_CONTINUES')
 def test_privacy_blocked(self):
  for context in [TrustedContext(),TrustedContext(sources=('gmail',),session_privacy='CLEAN'),TrustedContext(sources=('user_public',),session_privacy='PERSONAL'),TrustedContext(sources=('public_web',),session_privacy='CLEAN',tags=('credential',))]:
   calls=[];d=dispatch(context,reason='TOOL_VALIDATION_FAILED',payload='private',provider_config={'80b':'mock'},mock=calls.append)
   self.assertFalse(d['remote_call_permitted']);self.assertEqual(calls,[]);self.assertEqual(d['final_outcome'],'PRIVACY_BLOCKED')
 def test_public_mock_ladder(self):
  public=TrustedContext(sources=('user_public',),session_privacy='CLEAN');calls=[]
  d=dispatch(public,reason='TOOL_VALIDATION_FAILED',payload='unused',provider_config={'80b':'mock'},mock=calls.append)
  self.assertEqual(d['target'],'80b');self.assertEqual(d['final_outcome'],'MOCK_COMPLETED');self.assertEqual(len(calls),1)
  self.assertEqual(decide(TrustedContext(sources=('user_public',),session_privacy='CLEAN',current_tier='80b'),reason='VERIFICATION_FAILED')['target'],'235b')
 def test_complexity_and_missing_provider(self):
  d=decide(TrustedContext(sources=('user_public',),session_privacy='CLEAN',task='architecture'))
  self.assertEqual(d['target'],'235b');self.assertEqual(d['final_outcome'],'PROVIDER_NOT_CONFIGURED')
  d=decide(TrustedContext(),reason='TOOL_INCOMPATIBILITY_REPEATED',incompatibilities=1);self.assertFalse(d['escalation_required'])
 def test_no_model_confidence_or_untrusted_context(self):
  with self.assertRaises(TypeError):decide({'sources':['user_public'],'confidence':0.1})
  with self.assertRaises(ValueError):decide(TrustedContext(),reason='LOW_CONFIDENCE')
if __name__=='__main__':unittest.main()
