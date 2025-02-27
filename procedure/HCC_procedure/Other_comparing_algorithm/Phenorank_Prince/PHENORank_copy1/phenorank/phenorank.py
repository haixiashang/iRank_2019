#!/usr/bin/env python -B

#==============================================================================
#title          :phenorank.py
#description    :main function for running PhenoRank
#author         :Alex J Cornish
#date_created   :12 May 2015
#version        :0.1.2
#usage          :
#python_version :2.7.9
#==============================================================================

import cPickle
import logging
import numpy as np
import pandas as pd
import random
import pkg_resources
import scipy.sparse as sp
import scipy.stats as ss
import sys
import inout
import scoring

def run_phenorank(omim_obs, phenotypes_obs=None, nperm=1000, r=0.1, ni=20, gene_mask=None, include_h=True, include_m=True, dir_data="data_phenorank", filename_output="~"):
  """
  run the main PhenoRank function

  Args:
    omim_obs: OMIM ID for the disease of interest
    phenotypes_obs: a list of phenotypes describing the disease of interest
    nperm: number of permutations to complete
    r: the restart probability for the RWR method
    ic: the iteration cutoff for the RWR method
    gene_mask: gene to mask, if None no gene is masked
    include_h, include_m: logical values denoting whether human and mouse data should be included
    dir_data: path to the data, used for testing

  Returns:
    a pandas DataFrame of scores for the input GWAS loci
  """

  # create logger if required
  logger = logging.getLogger("__main__")

  # log algrithm progress
  logger.info("")
  logger.info("# Algorithm progress")
  logger.info("Importing data...")

  # import data
  con = open(pkg_resources.resource_filename("phenorank", dir_data + "/Reg_geID1.tsv"), "r")
  genes = list(pd.read_csv(con, header=None)[0])
  con.close()

  con = open(pkg_resources.resource_filename("phenorank", dir_data + "/phenorank_conditions.tsv"), "r")
  omims = list(pd.read_csv(con, header=None)[0])
  con.close()

  con = open(pkg_resources.resource_filename("phenorank", dir_data + "/phenorank_phenotypes.tsv"), "r")
  phenotypes = list(pd.read_csv(con, header=None)[0])
  con.close()

  con = open(pkg_resources.resource_filename("phenorank", dir_data + "/cp_h_omim.tsv"), "r")
  cp_h = inout.import_dictionary(con, split_by="|", key_int=True, value_int=True)
  con.close()

  con = open(pkg_resources.resource_filename("phenorank", dir_data + "/Reg_h.pickle"), "rb")
  gc_h = cPickle.load(con)
  con.close()

  con = open(pkg_resources.resource_filename("phenorank", dir_data + "/Reg_m.pickle"), "rb")
  gc_m = cPickle.load(con)
  con.close()

  con = open(pkg_resources.resource_filename("phenorank", dir_data + "/phenotype_ancestors.tsv"), "r")
  pheno_ancestors = inout.import_dictionary(con, split_by="|", key_int=True, value_int=True)
  con.close()

  con = open(pkg_resources.resource_filename("phenorank", dir_data + "/phenotype_ic.tsv"), "r")
  pheno_ic = np.array(list(pd.read_csv(con, header=None)[0]))
  con.close()

  con = open(pkg_resources.resource_filename("phenorank", dir_data + "/condition_ic.tsv"), "r")
  omim_ic = np.array(list(pd.read_csv(con, header=None)[0]))
  con.close()

  con = open(pkg_resources.resource_filename("phenorank", dir_data + "/pheno_condition_ic_matrix.pickle"), "rb")
  pheno_omim_ic_matrix = cPickle.load(con)
  con.close()

  con = open(pkg_resources.resource_filename("phenorank", dir_data + "/pheno_cooccur.pickle"), "rb")
  pheno_cooccur = cPickle.load(con)
  con.close()

  con = open(pkg_resources.resource_filename("phenorank", dir_data + "/Reg_net.pickle"), "rb")
  W = cPickle.load(con)
  con.close()

  # check when input is acceptable
  if omim_obs not in omims:
    raise Exception("disease " + omim_obs + " not accepted by PhenoRank")

  # get the indices of input genes, diseases and phenotypes
  logger.info("Indexing genes, diseases and phenotypes to consider...")
  if gene_mask:
    gene_mask_ind = genes.index(gene_mask)
  if omim_obs:
    omim_obs_ind = omims.index(omim_obs)
  if phenotypes_obs:
    phenotypes_obs_ind = [phenotypes.index(phenotype) for phenotype in phenotypes_obs]
  else:
    phenotypes_obs_ind = cp_h[omim_obs_ind]

  # if a gene to mask has been specified, and if it is associated with the OMIM ID, mask
  if gene_mask:
    gc_h[gene_mask_ind, omim_obs_ind] = 0

  # score genes using updated phenotypes
  logger.info("Scoring genes for query disease...")
  score_unprop, score_unranked_prop, score_obs = scoring.score_genes(phenotypes_obs_ind, pheno_ancestors, pheno_ic, omim_ic, pheno_omim_ic_matrix, gc_h, gc_m, W, r, ni, include_h, include_m)

  # score genes using permuted phenotypes
  score_sim = np.empty((nperm, len(score_obs))) # empty array to hold scores
  for n in range(nperm):
    pheno_sim_ind = scoring.simulate_disease(len(phenotypes_obs_ind), pheno_cooccur)
    tmp, tmp, score_sim[n] = scoring.score_genes(pheno_sim_ind, pheno_ancestors, pheno_ic, omim_ic, pheno_omim_ic_matrix, gc_h, gc_m, W, r, ni, include_h, include_m)
    if n != 0 and (n + 1) % 100 == 0: logger.info("Scoring genes for simulated sets of disease phenotype terms ({}/{} sets completed)...".format(n + 1, nperm))

  # compute p-values
  logger.info("Computing p-values...")
  pvalues = sum(score_sim >= score_obs) / float(nperm)
  pvalues[pvalues == 0.0] = 1.0 / nperm # ensure that no p-values equal 0

  # format output
  logger.info("Formatting results...")
  res = pd.DataFrame({"GENE": pd.Series(genes, index=genes), "SCORE_UNRANKED_UNPROP": pd.Series(score_unprop, index=genes), "SCORE_UNRANKED_PROP": pd.Series(score_unranked_prop, index=genes), "SCORE_RANKED_PROP": pd.Series(score_obs, index=genes), "PVALUE": pd.Series(pvalues, index=genes)})

  return res
