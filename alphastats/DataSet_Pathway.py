import os

from zmq import EVENT_HANDSHAKE_FAILED_NO_DETAIL
import plotly.express as px
import requests
import pandas as pd
from io import StringIO
from utils import check_internetconnection

class enrichement_df(pd.DataFrame):
    # this is that added methods dont get lost when operatons on pd Dataframe get performed
    @property
    def _constructor(self):
        return enrichement_df

    def plot_goterm(self):
        return px.scatter(self, 
            x = "FDR",
            y = "effect_size", 
            size = self["foreground_n"])



class Enrichment:
    @staticmethod
    def _extract_protein_ids(entry):
        try:
            proteins = entry.split(",")
            protein_id_list = []
            for protein in proteins:
                # 'sp|P0DMV9|HS71B_HUMAN,sp|P0DMV8|HS71A_HUMAN',
                if "|" in protein:
                    fasta_header_split = protein.split("|")
                else:
                    fasta_header_split = protein
                if isinstance(fasta_header_split, str):
                    #  'ENSEMBL:ENSBTAP00000007350',
                    if "ENSEMBL:" in fasta_header_split:
                        protein_id = fasta_header_split.replace("ENSEMBL:", "")
                    else:
                        protein_id = fasta_header_split
                else:
                    protein_id = fasta_header_split[1]
                protein_id_list.append(protein_id)
            protein_id_concentate = ";".join(protein_id_list)
            # ADD REV to the protein ID, else there will be duplicates in the ProteinGroup column
            if "REV_" in entry:
                protein_id_concentate = "REV_" + protein_id_concentate
        
        except AttributeError:
            protein_id_concentate = entry
        
        return protein_id_concentate

    def _get_ptm_proteins(self, sample=None):
        
        if self.evidence_df is None:
                raise ValueError("No informations about PTMs."
                "Either load a list of ProteinIDs containing PTMs"
                "or DataSet.load_ptm_df()")

        if "ProteinGroup" not in self.evidence_df.columns:
            self.evidence_df["ProteinGroup"] = self.evidence_df["Proteins"].map(self._extract_protein_ids)

        if isinstance(sample, str):
            protein_list = self.evidence_df[
            (self.evidence_df["Modifications"] != "Unmodified") & 
            (self.evidence_df["Experiment"]==sample)]["ProteinGroup"].to_list()
        
        elif isinstance(sample, list):
            protein_list = self.evidence_df[
            (self.evidence_df["Modifications"] != "Unmodified") & 
            (self.evidence_df["Experiment"].isin(sample))]["ProteinGroup"].to_list()   
        
        else:
            protein_list = self.evidence_df[self.evidence_df["Modifications"] != "Unmodified"]["ProteinGroup"].to_list()           
        
        protein_list = [str(x) for x in protein_list]
        return protein_list

    def _get_enriched_proteins(self):
        pass


    def go_characterize_foreground(self, tax_id=9606, protein_list=None):
        """Display existing functional annotations for your protein(s) of interest. 
        No statistical test for enrichment is performed.

        Args:
            tax_id (int, optional): _description_. Defaults to 9606.
            protein_list (_type_, optional): _description_. Defaults to None.

        Returns:
            _type_: _description_
        """
        check_internetconnection()

        if protein_list is None:
            protein_list = self._get_ptm_proteins()

        protein_list = "%0d".join(protein_list)
        url = r"https://agotool.org/api_orig"
        
        result = requests.post(url,
                   params={"output_format": "tsv",
                           "enrichment_method": "characterize_foreground",
                           "taxid": tax_id},
                   data={"foreground": protein_list})

        result_df = enrichement_df(pd.read_csv(StringIO(result.text), sep='\t')) 
        return result_df

   
   
    def go_abundance_correction(self, fg_sample, bg_sample, fg_protein_list=None):
        """his method was tailor-made to account for the inherent abundance bias is 
        Mass Spectromtry based shotgun-proteomics data (since proteins can't be amplified, 
        it will be more likely to detect highly abundant proteins compared to low abundant 
        proteins). This bias can influence GO-term enrichment analysis by showing enriched 
        terms for abundant rather than e.g. post-translationally-modified (PTM) proteins. 
        Please see the original Publication and the FAQ pages on 
        "How does the abundance_correction method work?". When should you use this method? 
        If you have PTM data or data that suffers from a similar bias. When comparing PTM 
        proteins to the genome (as the background) we've found abundance bias, simply 
        because a PTM will in most cases not be present at a stoichiometry of 100%. 
        Hence it is more likely to identify PTM proteins/peptides on abundant proteins 
        (rather than low abundant proteins) and therefore enrichment analysis will show 
        enrichment for abundant rather than modified proteins.

        Args:
            fg_sample (_type_): _description_
            bg_sample (_type_): _description_
            fg_protein_list (_type_, optional): _description_. Defaults to None.

        Returns:
            _type_: _description_
        """

        check_internetconnection()
        # get PTMs for fg_sample
        if fg_protein_list is None:
            fg_protein_list = self._get_ptm_proteins(sample = fg_sample)
        fg_protein_list = "%0d".join(fg_protein_list)

        # get intensity for bg_sample
        bg_protein = "%0d".join(self.mat.loc[bg_sample].index.to_list())
        bg_intensity = "%0d".join(self.mat.loc[bg_sample].values.tolist())

        url = r"https://agotool.org/api_orig"
        result = requests.post(url,
                   params={"output_format": "tsv",
                           "enrichment_method": "abundance_correction"},
                   data={"foreground": fg_protein_list,
                         "background": bg_protein,
                         "background_intensity": bg_intensity})
        result_df = enrichement_df(pd.read_csv(StringIO(result.text), sep='\t')) 
        return result_df
    
    
    def go_compare_groups(self, metadata_column, fg_group, bg_group):

        check_internetconnection()
        # get protein ids for groups
        fg_samples = self.metadata[self.metadata[metadata_column] == fg_group]["sample"].to_list()
        fg_proteins = "%0d".join(self._get_ptm_proteins(sample = fg_samples))
        
        bg_samples = self.metadata[self.metadata[metadata_column] == bg_group]["sample"].to_list()
        bg_proteins = "%0d".join(self._get_ptm_proteins(sample = bg_samples))
        
        url = r"https://agotool.org/api_orig"
        result = requests.post(url,
                   params={"output_format": "tsv",
                           "enrichment_method": "compare_samples"},
                   data={"foreground": fg_proteins,
                         "background": bg_proteins})
        result_df = enrichement_df(pd.read_csv(StringIO(result.text), sep='\t')) 
        return result_df

    def go_genome(self, tax_id=9606, method="ptm", sample = None, protein_list = None):
        
        check_internetconnection()
        
        if protein_list is None and method is "ptm":
            protein_list = self._get_ptm_proteins(sample = sample)
        
        if protein_list is None and method is "ttest":
            protein_list = self._get_enriched_proteins(sample = sample)

        protein_list = "%0d".join(protein_list)
        url = r"https://agotool.org/api_orig"
        
        result = requests.post(url,
                   params={"output_format": "tsv",
                           "enrichment_method": "genome",
                           "taxid": tax_id},
                   data={"foreground": protein_list})

        result_df = enrichement_df(pd.read_csv(StringIO(result.text), sep='\t')) 
        return result_df



    