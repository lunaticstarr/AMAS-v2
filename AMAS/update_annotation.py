#!/usr/bin/env python

# update_annotation.py
"""
Set annotation of a model file
Usage: python update_annotation.py BIOMD0000000190.xml species_rec.csv new_model.xml
"""
from xml.etree import ElementTree as ET
import argparse
import itertools
import libsbml
import numpy as np
import os
from os.path import dirname, abspath
import pandas as pd
import sys
sys.path.insert(0, dirname(dirname(abspath(__file__))))

from AMAS import constants as cn
from AMAS import annotation_maker as am
from AMAS import tools

def ensureMetaIdForComponents(model):
    """
    Ensure each component in the SBML model has a metaid.
    
    Parameters
    ----------
    model: libsbml.Model
        The SBML model to process.
    """
    # Function to generate a unique metaid
    def generateMetaId(index):
        return f"metaid_{index:07d}"  # Ensures a consistent format with leading zeros

    # Process species
    for i, species in enumerate(model.getListOfSpecies(), start=1):
        if not species.isSetMetaId():
            species.setMetaId(generateMetaId(i))

    # Process reactions
    for i, reaction in enumerate(model.getListOfReactions(), start=1):
        if not reaction.isSetMetaId():
            reaction.setMetaId(generateMetaId(i + len(model.getListOfSpecies())))

    # Process genes
    try:
        for i, gene in enumerate(model.getPlugin("fbc").getListOfGeneProducts(), start=1):
            if not gene.isSetMetaId():
                gene.setMetaId(generateMetaId(i))
    except:
        pass

    # Process qualitative species
    try:
        for i, qual_spec in enumerate(model.getPlugin("qual").getListOfQualitativeSpecies(), start=1):
            if not qual_spec.isSetMetaId():
                qual_spec.setMetaId(generateMetaId(i))
    except:
        pass

def main():
  parser = argparse.ArgumentParser(description='Update annotations of a model using user\'s feedback file (.csv)')
  parser.add_argument('infile', type=str, help='path of a model file (.xml or .sbml) to update annotation')
  parser.add_argument('feedback', type=str, help='path of the file (.csv) containing user\'s feedback')
  parser.add_argument('outfile', type=str, help='file path to save model with updated annotations')
  parser.add_argument('--convert', type=str, help='whether to convert existing annotations or not. ' +\
                                                  'If Y or yes is given, existing annotations in "isDescribedBy" will be converted to "is"' +\
                                                  'N or no will not modify annotations in "isDescribedBy".',
                                            nargs='?',
                                            default='yes')
  # csv file with user choice
  args = parser.parse_args()
  infile = args.infile
  feedback = args.feedback
  outfile = args.outfile
  convert = args.convert
  user_csv = pd.read_csv(feedback)

  if convert.lower() in ['y', 'yes']:
    print("Converting existing annotations in 'isDescribedBy' to 'is'...")

  # Read the SBML file
  reader = libsbml.SBMLReader()
  document = reader.readSBML(infile)
  model = document.getModel()
                   
  if model.getPlugin("qual"):
    ELEMENT_FUNC = {'qual_species': model.getPlugin("qual").getQualitativeSpecies}
  else:
    if model.getPlugin("fbc"):
      ELEMENT_FUNC = {'species': model.getSpecies,
                      'reaction': model.getReaction,
                      'genes':model.getPlugin("fbc").getGeneProduct}
    else:
      ELEMENT_FUNC = {'species': model.getSpecies,
                      'reaction': model.getReaction}

  # Ensure all components have metaids
  ensureMetaIdForComponents(model)

  # Only takes cells with values 'add' or 'delete'
  chosen = user_csv[(user_csv['UPDATE ANNOTATION']=='add') |\
                   (user_csv['UPDATE ANNOTATION']=='delete')]

  element_types = list(np.unique(chosen['type']))
  for one_type in element_types:
    maker = am.AnnotationMaker(one_type)
    ACTION_FUNC = {'delete': maker.deleteAnnotation,
                   'add': maker.addAnnotation}
    df_type = chosen[chosen['type']==one_type]
    # Update metaids in df_type
    df_type['meta id'] = df_type['id'].apply(lambda x: ELEMENT_FUNC[one_type](str(x)).getMetaId())
    uids = list(np.unique(df_type['id']))
    meta_ids = {val:list(df_type[df_type['id']==val]['meta id'])[0] for val in uids}
    # going through one id at a time
    for one_id in uids:
      orig_str = ELEMENT_FUNC[one_type](one_id).getAnnotationString()

      df_id = df_type[df_type['id']==one_id]
      dels = list(df_id[df_id[cn.DF_UPDATE_ANNOTATION_COL]=='delete'].loc[:, 'annotation'])
      dels = [str(val) for val in dels]
      adds_raw = list(df_id[df_id[cn.DF_UPDATE_ANNOTATION_COL]=='add'].loc[:, 'annotation'])
      # existing annotations to be kept 
      keeps = list(df_id[df_id[cn.DF_UPDATE_ANNOTATION_COL]=='keep'].loc[:, 'annotation'])
      adds = list(set(adds_raw + keeps))
      adds = [str(val) for val in adds]

      # convert existing annotations in 'isDescribedBy' to 'is'
      # original annotations are kept in 'isDescribedBy'
      if convert.lower() in ['y', 'yes']:
        orig_str = maker.convertIsDescribedByToIs(orig_str, meta_ids[one_id])

      # if type is 'reaction', need to map rhea terms back to ec/kegg terms to delete them. 
      if one_type == 'reaction':
        rhea_del_terms = list(set(itertools.chain(*[tools.getAssociatedTermsToRhea(val) for val in dels])))
        deled = maker.deleteAnnotation(rhea_del_terms, orig_str)
      elif one_type == 'species' or one_type == 'genes' or one_type == 'qual_species' :
        deled = maker.deleteAnnotation(dels, orig_str)

      print('deled:')
      print(deled)
      added = maker.addAnnotation(adds, deled, meta_ids[one_id])

      print('added:')
      print(added)
      
      ELEMENT_FUNC[one_type](one_id).setAnnotation(added)
      new_annot = ELEMENT_FUNC[one_type](one_id).getAnnotationString()
  libsbml.writeSBMLToFile(document, outfile)
  print("...\nUpdated model file saved as:\n%s\n" % os.path.abspath(outfile))


if __name__ == '__main__':
  main()