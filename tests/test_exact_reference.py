"""Unrelated synthetic endpoints only; no actual study data or bootstrap."""
from decimal import Decimal
from itertools import product
from statistics import mean
import unittest
from scripts.exact_reference import exact_reference

def row(i,f,x,y):return {'unit':str(i),'family':f,'values':{'x':x,'y':y}}
class ExactTests(unittest.TestCase):
 def test_unrelated_decimal_ties_inclusive(self):
  rs=[row(0,'u',0,.1),row(1,'v',.2,.3),row(2,'w',.7,.6),*[row(i,'z'+str(i),0,0) for i in range(3,6)]]
  result=exact_reference(rs,['x','y'])['contrasts'][0];self.assertEqual(result['inclusive_tail_assignments'],64);self.assertEqual(result['sign_flip_reference']['two_sided_p'],1)
  ds=[.1,.3-.2,.6-.7,0,0,0];naive=sum(abs(mean(d*s for d,s in zip(ds,ss)))>=abs(mean(ds)) for ss in product([-1,1],repeat=6))/64;self.assertEqual(naive,.75)
 def test_equal_family_weights_not_row_weights(self):
  rs=[row(i,'large',0,1) for i in range(10)]+[row(10,'small',1,0)];r=exact_reference(rs,['x','y']);self.assertEqual(r['contrasts'][0]['exact_estimate'],'0');self.assertEqual(r['common_units'],11)
 def test_explicit_nulls_remain_unavailable(self):
  r=exact_reference([row(0,'a',None,1),row(1,'b',0,1)],['x','y']);self.assertEqual(r['common_families'],1);self.assertEqual(r['unmatched_units'],['0']);self.assertEqual(r['contrasts'][0]['sign_flip_reference'],{'assignments':2,'two_sided_p':1})
 def test_no_common_family(self):
  r=exact_reference([row(0,'a',None,1)],['x','y']);self.assertIsNone(r['contrasts'][0]['sign_flip_reference']);self.assertEqual(r['common_families'],0)
 def test_zero_differences_all_in_tail(self):
  r=exact_reference([row(i,str(i),Decimal('.37'),Decimal('.37')) for i in range(4)],['x','y']);self.assertEqual(r['contrasts'][0]['inclusive_tail_assignments'],16)
 def test_all_arm_common_cohort_for_every_contrast(self):
  rs=[{'unit':'0','family':'a','values':{'x':1,'y':2,'z':None}},{'unit':'1','family':'b','values':{'x':1,'y':2,'z':3}}];r=exact_reference(rs,['x','y','z']);self.assertEqual(r['common_units'],1);self.assertEqual(len(r['contrasts']),3);self.assertTrue(all(v['sign_flip_reference']['assignments']==2 for v in r['contrasts']))
 def test_invalid_numeric_inputs_rejected(self):
  for v in [True,float('inf'),float('nan'),Decimal('NaN')]:
   with self.subTest(value=type(v).__name__),self.assertRaises(ValueError):exact_reference([row(0,'a',v,1)],['x','y'])
 def test_duplicate_unit_rejected(self):
  with self.assertRaises(ValueError):exact_reference([row(0,'a',0,1),row(0,'b',0,1)],['x','y'])
if __name__=='__main__':unittest.main(verbosity=2)
