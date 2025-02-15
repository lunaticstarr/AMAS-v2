# test_recommender.py
# unittest for AMAS.recommender

import libsbml
import numpy as np
import os
import pandas as pd
import sys
import unittest
from unittest.mock import mock_open, patch


from AMAS import constants as cn
from AMAS import recommender
from AMAS import species_annotation as sa
from AMAS import tools

BIOMD_17_PATH = os.path.join(cn.TEST_DIR, 'BIOMD0000000017.xml')
BIOMD_190_PATH = os.path.join(cn.TEST_DIR, 'BIOMD0000000190.xml')
BIOMD_634_PATH = os.path.join(cn.TEST_DIR, 'BIOMD0000000634.xml')
E_COLI_PATH = os.path.join(cn.TEST_DIR, 'e_coli_core.xml')
ONE_SPEC_CAND = ('CHEBI:15414', 1.0)
ONE_SPEC_URL = 'https://www.ebi.ac.uk/chebi/searchId.do?chebiId=CHEBI%3A15414'
TWO_SPEC_CAND = ('CHEBI:15729', 1.0)
TWO_SPEC_URL = 'https://www.ebi.ac.uk/chebi/searchId.do?chebiId=CHEBI%3A15729'

ONE_REAC_CAND = ('RHEA:22964', 1.0)
ONE_REAC_URL = 'https://www.rhea-db.org/rhea/22964'

SPECIES_SAM = 'SAM'
SPECIES_SAM_NAME = 'S-adenosyl-L-methionine'
SPECIES_ORN = 'ORN'
SPECIES_ATP = 'ATP'
REACTION_ODC = 'ODC'
REACTION_SAMDC = 'SAMdc'
REACTION_SPMS = 'SpmS'
R_PFK = 'R_PFK'
R_PFL = 'R_PFL'
ECOLI_REACTIONS = [R_PFK, R_PFL]
ECOLI_ATP = 'M_atp_c'
ECOLI_RHEA = 'RHEA:12420'

ONE_CHEBI = 'CHEBI:15414'
ATP_CHEBI = 'CHEBI:30616'
FORMULA_ATP = 'C10N5O13P3'


RESULT_RECOM = cn.Recommendation('R_PFK',
                                 [('RHEA:12420', 0.6), ('RHEA:13377', 0.6)],
                                 ['https://www.rhea-db.org/rhea/12420', 'https://www.rhea-db.org/rhea/13377'],
                                 ['tagatose-6-phosphate kinase activity', 'phosphoglucokinase activity'])
RESULT_MARKDOWN = '                                   R_PFK                                    \n' + \
                  '+----+--------------+---------------+--------------------------------------+\n' + \
                  '|    | annotation   |   match score | label                                |\n' + \
                  '+====+==============+===============+======================================+\n' + \
                  '|  0 | RHEA:12420   |         0.600 | tagatose-6-phosphate kinase activity |\n' + \
                  '+----+--------------+---------------+--------------------------------------+\n' + \
                  '|  1 | RHEA:13377   |         0.600 | phosphoglucokinase activity          |\n' + \
                  '+----+--------------+---------------+--------------------------------------+'

RESULT_MARKDOWN_SAMdc = '                                      SAMdc                                      \n' +\
                        '+----+--------------+---------------+-------------------------------------------+\n' +\
                        '|    | annotation   |   match score | label                                     |\n' +\
                        '+====+==============+===============+===========================================+\n' +\
                        '|  0 | RHEA:15981   |         0.500 | adenosylmethionine decarboxylase activity |\n' +\
                        '+----+--------------+---------------+-------------------------------------------+\n'

RESULT_MARKDOWN_A = '                               A                                \n' +\
                    '+----+--------------+---------------+--------------------------+\n' +\
                    '|    | annotation   |   match score | label                    |\n' +\
                    '+====+==============+===============+==========================+\n' +\
                    '|  0 | CHEBI:15625  |         1.000 | S-adenosylmethioninamine |\n' +\
                    '+----+--------------+---------------+--------------------------+\n'

#############################
# Tests
#############################
class TestRecommender(unittest.TestCase):
  def setUp(self):
    self.recom = recommender.Recommender(libsbml_fpath=BIOMD_190_PATH)
    self.recom17 = recommender.Recommender(libsbml_fpath=BIOMD_17_PATH)  

  def testGetDataFrameFromRecommendation(self):
    df = self.recom.getDataFrameFromRecommendation(rec=RESULT_RECOM,
                                                   show_url=False)
    self.assertEqual(set(df.index), {0,1})

  def testGetRecommendationFromDataFrame(self):
    df = self.recom.getDataFrameFromRecommendation(rec=RESULT_RECOM,
                                                   show_url=False)
    rec = self.recom.getRecommendationFromDataFrame(df)
    self.assertEqual(rec, RESULT_RECOM)

  def testGetMarkdownFromRecommendation(self):
    res = self.recom.getMarkdownFromRecommendation(rec=RESULT_RECOM,
                                                   show_url=False)
    self.assertEqual(res, RESULT_MARKDOWN)

  def testGetSpeciesRecommendation(self):
    one_res = self.recom.getSpeciesRecommendation(pred_id=SPECIES_SAM,
                                                  update=False,
                                                  method='edist')
    self.assertEqual(one_res.id, SPECIES_SAM)
    self.assertTrue(ONE_SPEC_CAND in one_res.candidates)
    self.assertTrue(ONE_SPEC_URL in one_res.urls)
    self.assertEqual(self.recom.species.candidates, {})
    self.assertEqual(self.recom.species.formula, {})
    two_res = self.recom.getSpeciesRecommendation(pred_str=SPECIES_SAM_NAME,
                                                  update=True,
                                                  method='cdist')
    self.assertEqual(two_res.id, SPECIES_SAM_NAME)
    self.assertTrue(ONE_SPEC_CAND in two_res.candidates)
    self.assertTrue(ONE_SPEC_URL in two_res.urls)
    self.assertTrue((ONE_CHEBI, 1.0) in self.recom.species.candidates[SPECIES_SAM_NAME])
    one_formula = cn.REF_CHEBI2FORMULA[ONE_CHEBI]
    self.assertTrue(one_formula in self.recom.species.formula[SPECIES_SAM_NAME])    

  def testGetSpeciesIDs(self):
    one_res = self.recom.getSpeciesIDs(pattern="*CoA")
    self.assertTrue('AcCoA' in one_res)
    self.assertTrue('CoA' in one_res)
    self.assertEqual(len(one_res), 2)
    none_res = self.recom.getSpeciesIDs(pattern="AAA")
    self.assertEqual(none_res, None)

  def testGetSpeciesListRecommendation(self):
    specs = self.recom.getSpeciesListRecommendation(pred_ids=[SPECIES_SAM, SPECIES_ORN],
                                                    update=False, method='edist')
    one_res = specs[1]
    self.assertEqual(one_res.id, SPECIES_ORN)
    self.assertTrue(TWO_SPEC_CAND in one_res.candidates)
    self.assertTrue(TWO_SPEC_URL in one_res.urls)
    self.assertEqual(self.recom.species.candidates, {})
    self.assertEqual(self.recom.species.formula, {})
    two_specs = self.recom.getSpeciesListRecommendation(pred_ids=[SPECIES_SAM, SPECIES_ORN],
                                                        update=True, method='cdist')
    self.assertTrue((ONE_CHEBI, 1.0) in self.recom.species.candidates[SPECIES_SAM])
    one_formula = cn.REF_CHEBI2FORMULA[ONE_CHEBI]
    self.assertTrue(one_formula in self.recom.species.formula[SPECIES_SAM])      

  def testGetReactionRecommendation(self):
    one_res = self.recom.getReactionRecommendation(REACTION_ODC)
    self.assertEqual(one_res.id, REACTION_ODC)
    self.assertTrue(ONE_REAC_CAND in one_res.candidates)
    self.assertTrue(ONE_REAC_URL in one_res.urls)

  def testGetReactionIDs(self):
    one_res = self.recom.getReactionIDs(pattern='*CoA', by_species=True)
    self.assertEqual(len(one_res), 4)
    self.assertTrue('SSAT_for_S' in one_res)
    two_res = self.recom.getReactionIDs(pattern='*CoA', by_species=False)
    self.assertEqual(len(two_res), 2)
    self.assertTrue('VCoA' in two_res)

  def testGetReactionListRecommendation(self):
    reacs = self.recom.getReactionListRecommendation(pred_ids=[REACTION_ODC, REACTION_SAMDC])
    one_res = reacs[0]
    self.assertEqual(one_res.id, REACTION_ODC)
    self.assertTrue(ONE_REAC_CAND in one_res.candidates)
    self.assertTrue(ONE_REAC_URL in one_res.urls)

  def testParseSBML(self):
    reader = libsbml.SBMLReader()
    document = reader.readSBML(BIOMD_190_PATH)
    dummy_recom = recommender.Recommender(libsbml_cl=document)
    # checking if model was loaded successfully
    self.assertEqual(len(dummy_recom.species.names), 11)
    self.assertEqual(len(dummy_recom.reactions.reaction_components), 13)
    self.assertTrue(SPECIES_SAM in dummy_recom.species.names.keys())
    self.assertTrue(REACTION_ODC in dummy_recom.reactions.reaction_components.keys())
    self.assertEqual(len(dummy_recom.species.exist_annotation), 11)
    self.assertEqual(len(dummy_recom.reactions.exist_annotation), 9)

  def testGetSpeciesStatistics(self):
    recom2 = recommender.Recommender(libsbml_fpath=BIOMD_634_PATH)
    spec_stats1 = recom2.getSpeciesStatistics(model_mean=True)
    self.assertEqual(spec_stats1[cn.RECALL], 1.000)
    self.assertEqual(spec_stats1[cn.PRECISION], 0.125)
    spec_stats2 = recom2.getSpeciesStatistics(model_mean=False)
    self.assertEqual(spec_stats2[cn.RECALL][SPECIES_ATP], 1.000)
    self.assertEqual(spec_stats2[cn.PRECISION][SPECIES_ATP], 0.200)

  def testGetReactionStatistics(self):
    reac_stats1 = self.recom.getReactionStatistics(model_mean=True)
    self.assertEqual(reac_stats1[cn.RECALL], 0.694)
    self.assertEqual(reac_stats1[cn.PRECISION], 0.631)
    reac_stats2 = self.recom.getReactionStatistics(model_mean=False)
    self.assertEqual(reac_stats2[cn.RECALL][REACTION_SPMS], 1.000)
    self.assertEqual(reac_stats2[cn.PRECISION][REACTION_SPMS], 0.333)

  def testAutoSelectAnnotation(self):
    cutoff = 0.6
    res1 = self.recom.getSpeciesRecommendation(pred_id=SPECIES_SAM, get_df=True)
    df1 = self.recom.autoSelectAnnotation(res1, cutoff)
    self.assertEqual(df1.shape[0], 2)
    self.assertEqual(set(df1[cn.DF_MATCH_SCORE_COL]), {1.0})
    res2 = self.recom.getReactionRecommendation(pred_id=REACTION_SAMDC, get_df=True)
    df2 = self.recom.autoSelectAnnotation(res2, cutoff)
    self.assertEqual(df2.shape[0], 0)

  def testFilterDataFrameByThreshold(self):
    df = self.recom.getDataFrameFromRecommendation(RESULT_RECOM)
    res1 = self.recom.filterDataFrameByThreshold(df, min_score=0.6)
    res2 = self.recom.filterDataFrameByThreshold(df, min_score=0.7)
    self.assertEqual(list(np.unique(res1[cn.DF_MATCH_SCORE_COL])), [0.6])
    self.assertEqual(list(np.unique(res2[cn.DF_MATCH_SCORE_COL])), [])

  def testRecommendReactions(self):
    inp_reactions = [REACTION_ODC, REACTION_SAMDC]
    recomt = self.recom.recommendReactions(ids=inp_reactions)
    self.assertEqual(len(recomt.columns), 10)
    self.assertTrue('UPDATE ANNOTATION' in recomt.columns)
    self.assertEqual(recomt.shape, (4,10))
    self.assertEqual(set(recomt['id']), set(inp_reactions))
    self.assertEqual(set(recomt['UPDATE ANNOTATION']),
                     {'keep', 'ignore'})
    with patch("builtins.print") as mock_print:
      recomt2 = self.recom.recommendReactions(ids=inp_reactions,
                                              min_len=10000)
    res_str = 'No reaction after the element filter.\n'
    mock_print.assert_called_once_with(res_str)

  def testRecommendAnnotation(self): 
    one_res = self.recom17.recommendAnnotation(optimize=False)
    one_sub_df = one_res[one_res['id']=='AcetoinIn']
    self.assertTrue('CHEBI:2430' in set(one_sub_df['annotation']))
    self.assertTrue('CHEBI:15688' in set(one_sub_df['annotation']))
    two_res = self.recom17.recommendAnnotation(optimize=True)
    two_sub_df = two_res[two_res['id']=='AcetoinIn']
    self.assertTrue('CHEBI:15378' in set(two_sub_df['annotation']))
    self.assertTrue('CHEBI:15688' in set(two_sub_df['annotation']))

  def testRecommendSpecies(self):
    inp_species = [SPECIES_SAM, SPECIES_ORN]
    recomt = self.recom.recommendSpecies(ids=inp_species)
    self.assertEqual(len(recomt.columns), 10)
    self.assertTrue('UPDATE ANNOTATION' in recomt.columns)
    self.assertEqual(recomt.shape, (4,10))
    self.assertEqual(set(recomt['id']), set(inp_species))
    self.assertEqual(set(recomt['UPDATE ANNOTATION']),
                     {'keep', 'ignore'})
    with patch("builtins.print") as mock_print:
      recomt2 = self.recom.recommendSpecies(ids=inp_species,
                                            min_len=10000)
    res_str = 'No species after the element filter.\n'
    mock_print.assert_called_once_with(res_str)

  def testUpdateCurrentElementType(self):
    self.recom.updateCurrentElementType(element_type='species')
    self.assertEqual(self.recom.current_type, 'species')

  def testUpdateJustDisplayed(self):
    exist_displayed = self.recom.just_displayed
    self.assertEqual(exist_displayed, None)
    df = self.recom.getSpeciesRecommendation(pred_id=SPECIES_SAM,
                                             get_df=True)
    self.recom.updateJustDisplayed({SPECIES_SAM: df})
    self.assertEqual({SPECIES_SAM: df}, self.recom.just_displayed)

  def testSelectAnnotation(self):
    df = self.recom.getSpeciesRecommendation(pred_id=SPECIES_SAM,
                                             get_df=True)
    self.recom.updateJustDisplayed({SPECIES_SAM: df})
    self.recom.updateCurrentElementType(element_type='species')
    with patch("builtins.print") as mock_print:
      self.recom.selectAnnotation((SPECIES_SAM, 1))
    mock_print.assert_called_once_with("Selection updated.")
    self.assertTrue(SPECIES_SAM in self.recom.selection['species'].keys())
    filt_df = df.loc[[1], :]
    res = self.recom.selection['species'][SPECIES_SAM]
    # test if filt_df and res are equal
    for one_col in res.columns:
      self.assertEqual(res.loc[1, one_col], filt_df.loc[1, one_col])

  def testDisplaySelection(self):
    df = self.recom.getSpeciesRecommendation(pred_id=SPECIES_SAM,
                                             get_df=True)
    self.recom.selection['species'] = {SPECIES_SAM: df}
    with patch("builtins.print") as mock_print:
      self.recom.displaySelection()
    res_str = self.recom.getMarkdownFromRecommendation(df)+"\n"  
    mock_print.assert_called_once_with(res_str)

  def testGetRecomTable(self):
    inp_species = [SPECIES_SAM, SPECIES_ORN]
    df = self.recom.getSpeciesListRecommendation(pred_ids=inp_species,
                                                 get_df=True)
    recomt = self.recom.getRecomTable('species', df)
    self.assertEqual(len(recomt.columns), 10)
    self.assertTrue('UPDATE ANNOTATION' in recomt.columns)
    self.assertEqual(recomt.shape, (4,10))
    self.assertEqual(set(recomt['id']), set(inp_species))
    self.assertEqual(set(recomt['UPDATE ANNOTATION']),
                     {'keep', 'ignore'})

  def testGetSBMLDocument(self):
    pred = self.recom.recommendSpecies(ids=None,
                                       mssc='top',
                                       cutoff=0.0)
    res_doc = self.recom.getSBMLDocument(sbml_document=self.recom.sbml_document,
                                         chosen=pred,
                                         auto_feedback=True)
    model = res_doc.getModel()
    upd_spec_anot = tools.extractExistingSpeciesAnnotation(model)
    self.assertEqual(set(upd_spec_anot['SAM']), {'CHEBI:15414', 'CHEBI:59789'})

  def testOptimizePrediction(self): 
    specs = self.recom17.getSpeciesIDs()
    res_spec = self.recom17.getSpeciesListRecommendation(pred_ids=specs,
                                                         get_df=True)
    reacts = self.recom17.getReactionIDs() 
    res_reac = self.recom17.getReactionListRecommendation(pred_ids=reacts,
                                                          get_df=True)
    opt_recom = self.recom17.optimizePrediction(pred_spec=res_spec,
                                                pred_reac=res_reac)
    sub_recom = opt_recom[opt_recom['id']=='AcetoinIn']
    self.assertTrue('AcetoinIn' in np.unique(opt_recom['id']))
    self.assertTrue('CHEBI:15378' in set(sub_recom['annotation']))

 
  def testSaveToCSV(self):
    df = self.recom.getSpeciesListRecommendation(pred_ids=['SAM'],
                                                 get_df=True)
    res = self.recom.getRecomTable('species', df)
    self.recom.saveToCSV(res, "test.csv")
    new_df = pd.read_csv("test.csv")
    self.assertEqual(new_df.loc[0, 'file'], 'BIOMD0000000190.xml')
    self.assertEqual(new_df.loc[0, 'type'], 'species')
    self.assertEqual(new_df.loc[0, 'display name'], 'S-adenosyl-L-methionine')
    self.assertEqual(new_df.loc[0, 'annotation'], 'CHEBI:15414')
    self.assertEqual(new_df.loc[0,  cn.DF_UPDATE_ANNOTATION_COL], 'keep')
    os.remove("test.csv")

  # def testSaveToSBML(self):
  #   one_dict = {'annotation':['CHEBI:15414'],
  #               'match score': [1.0],
  #               'label': ['S-adenosyl-L-methionine']}
  #   one_df = pd.DataFrame(one_dict)
  #   one_df.index = [2]
  #   one_df.index.name = 'SAM'
  #   self.recom.selection['species'] = {SPECIES_SAM: one_df}
  #   self.recom.saveToSBML("test_sbml.xml")
  #   recom2 = recommender.Recommender(libsbml_fpath='test_sbml.xml')
  #   self.assertEqual(recom2.species.exist_annotation[SPECIES_SAM], ['CHEBI:15414'])
  #   os.remove("test_sbml.xml")

  def testPrintSummary(self):
    with patch("builtins.print") as mock_print:
      self.recom.printSummary(saved=['SAM', 'A'],
                              element_type='species')
    res_str1 = 'Annotation recommended for 2 species:\n[SAM, A]\n'
    mock_print.assert_called_once_with(res_str1)
    #
    with patch("builtins.print") as mock_print:
      self.recom.printSummary(saved=['ODC', 'SAMdc', 'SSAT_for_S'],
                              element_type='reaction')
    res_str2 = 'Annotation recommended for 3 reaction(s):\n[ODC, SAMdc, SSAT_for_S]\n'
    mock_print.assert_called_once_with(res_str2)

  def testGetMatchScoreOfCHEBI(self):
    chebi_score = self.recom.getMatchScoreOfCHEBI(inp_id=SPECIES_SAM,
                                                  inp_chebi='CHEBI:15414')
    self.assertEqual(chebi_score, 1.0)

  def testGetMatchScoreOfRHEA(self):
    rhea_score = self.recom.getMatchScoreOfRHEA(inp_id='SSAT_for_S',
                                                inp_rhea='RHEA:33099')
    self.assertEqual(rhea_score, 0.8)