"""Independent JSON scorer checks: errors, schema violations and valid tool steps."""
import unittest
from fork.evaluate_json import evaluate,summarize,validator

SCHEMA={'type':'object','properties':{'result':{'type':'integer'}},'required':['result'],'additionalProperties':False}
CASE={'group':'stress','body':{'response_format':{'type':'json_schema','json_schema':{'name':'test','schema':SCHEMA}}},'expected':{}}

def response(text,finish='stop',calls=None):
 return {'choices':[{'message':{'content':text,'tool_calls':calls or []},'finish_reason':finish}],
         'usage':{'completion_tokens':8},'timings':{'predicted_per_second':50}}


class JSONEvidence(unittest.TestCase):
 def test_invalid_syntax_is_distinct_from_http_failure(self):
  r=evaluate(CASE,200,response('```json\n{"result":42}\n```'))
  self.assertEqual(r['category'],'invalid_json_syntax');self.assertFalse(r['passed'])
  r=evaluate(CASE,502,{'error':{'type':'structured_output_failed','message':'invalid JSON'}})
  self.assertEqual(r['category'],'structured_output_failed');self.assertIsNone(r['json_valid'])

 def test_schema_types_required_and_extra_fields_are_independently_checked(self):
  for text in ['{}','{"result":"42"}','{"result":42,"extra":true}']:
   with self.subTest(text=text):
    r=evaluate(CASE,200,response(text));self.assertTrue(r['json_valid']);self.assertFalse(r['schema_valid'])
    self.assertEqual(r['category'],'schema_violation');self.assertTrue(r['schema_errors'])
  self.assertTrue(evaluate(CASE,200,response('{"result":42}'))['passed'])

 def test_nonstandard_json_constants_and_root_types_are_not_accepted(self):
  self.assertEqual(evaluate(CASE,200,response('{"result":NaN}'))['category'],'invalid_json_syntax')
  self.assertEqual(evaluate(CASE,200,response('[42]'))['category'],'schema_violation')

 def test_schema_pass_is_not_value_correctness(self):
  case={**CASE,'expected':{'value':{'result':42}}}
  r=evaluate(case,200,response('{"result":17}'));self.assertTrue(r['schema_valid'])
  self.assertEqual(r['category'],'wrong_value');self.assertFalse(r['passed'])

 def test_tool_step_does_not_need_final_json_but_requires_valid_expected_call(self):
  tool={'type':'function','function':{'name':'sql_query','parameters':{'type':'object',
        'properties':{'query':{'type':'string'}},'required':['query'],'additionalProperties':False}}}
  case={**CASE,'body':{**CASE['body'],'tools':[tool]},'expected':{'kind':'tool','tool':'sql_query','arguments':{'query':'SELECT 1'}}}
  call={'function':{'name':'sql_query','arguments':'{"query":"SELECT 1;"}'}}
  r=evaluate(case,200,response(None,'tool_calls',[call]));self.assertTrue(r['passed']);self.assertIsNone(r['json_valid'])
  call={'function':{'name':'sql_queri','arguments':'{"query":"SELECT 1"}'}}
  self.assertEqual(evaluate(case,200,response(None,'tool_calls',[call]))['category'],'wrong_tool')

 def test_expected_400_is_a_negative_control_not_a_json_failure(self):
  case={**CASE,'group':'negative','expected':{'http_status':400}}
  self.assertTrue(evaluate(case,400,{'error':{'type':'invalid_request_error'}})['passed'])
  self.assertFalse(evaluate(case,500,{'error':{'type':'server_error'}})['passed'])

 def test_truncated_valid_json_does_not_pass(self):
  r=evaluate(CASE,200,response('{"result":42}','length'))
  self.assertEqual(r['category'],'incomplete_generation');self.assertFalse(r['passed'])

 def test_only_successful_nonwarmups_count_for_speed(self):
  good={'case_id':'perf','group':'performance','warmup':False,'evaluation':{'passed':True,'category':'json_success'},'metrics':{'seconds':1}}
  bad={**good,'evaluation':{'passed':False,'category':'api_error'},'metrics':{'seconds':0.01}}
  warm={**good,'warmup':True,'metrics':{'seconds':10}}
  p=summarize([good,bad,warm])['performance']['perf'];self.assertEqual(p['successful'],1);self.assertEqual(p['seconds']['median'],1)


if __name__=='__main__':unittest.main()
