import unittest
import pandas as pd
import logging
from unittest.mock import patch
import logging


from alphastats.loader.BaseLoader import BaseLoader
from alphastats.loader.DIANNLoader import DIANNLoader
from alphastats.loader.MaxQuantLoader import MaxQuantLoader
from alphastats.loader.AlphaPeptLoader import AlphaPeptLoader
from alphastats.loader.FragPipeLoader import FragPipeLoader
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class BaseTestLoader:
    #  parent class of test loader for common tests among loaders
    # this is wrapped in a nested class so it doesnt get called separatly when testing
    # plus to avoid multiple inheritance
    class BaseTest(unittest.TestCase):
        @contextmanager
        def assertNotRaises(self, exc_type):
            try:
                yield None
            except exc_type:
                raise self.failureException("{} raised".format(exc_type.__name__))

        def test_dataformat(self):
            # check if loaded data is pandas dataframe
            self.assertIsInstance(self.obj.rawinput, pd.DataFrame)

        def test_check_if_columns_are_present_error(self):
            # check if columns are present
            # check if error gets raised when column is not present
            with self.assertRaises(KeyError):
                self.obj.confidence_column = "wrong_column"
                self.obj._check_if_columns_are_present()

        def test_check_if_columns_are_present_no_error(self):
            # check if columns are present
            # check if error gets raised when column is not present
            with self.assertNotRaises(KeyError):
                self.obj._check_if_columns_are_present()

        @patch("logging.Logger.warning")
        def test_check_if_indexcolumn_is_unique_warning(self, mock):
            #  check if indexcolumn is unique
            # check if error gets raised when duplicate
            self.obj.rawinput[self.obj.index_column] = "non unique"
            self.obj._check_if_indexcolumn_is_unique()
            mock.assert_called_once()

        # @patch("logging.Logger.warning")
        # def test_check_if_indexcolumn_is_unique_no_warning(self,mock):
        #  check if indexcolumn is unique
        # self.obj.check_if_indexcolumn_is_unique()
        # mock.assert_not_called()

        def test_check_if_file_exists(self):
            # check if error gets raised when file doesnt exist
            with self.assertRaises(OSError):
                wrong_file_path = "wrong/file/path"
                self.obj._check_if_file_exists(file=wrong_file_path)

        def test_add_contaminantion_column(self):
            column_added = "contamination_library" in self.obj.rawinput
            self.assertTrue(column_added)
            self.assertEqual(self.obj.rawinput["contamination_library"].dtype, "bool")

        def test_df_dimensions(self):
            # test if dataframe gets loaded correctly
            # are there as many rows and column we expect
            self.assertEqual(self.obj.rawinput.shape, self.df_dim)


class TestAlphaPeptLoader(BaseTestLoader.BaseTest):
    def setUp(self):
        self.obj = AlphaPeptLoader(file="testfiles/alphapept/results_proteins.csv")
        self.hdf_file = "testfiles/alphapept/results.hdf"
        # expected dim of rawinput df
        self.df_dim = (3781, 8)

    def test_load_hdf_protein_table(self):
        hdf_format = AlphaPeptLoader(file=self.hdf_file)
        # test if hdf file gets loaded
        self.assertEqual(hdf_format.rawinput.shape, self.df_dim)

    def test_add_contamination_reverse_column(self):
        # check if contamination column has been added
        column_added = "Reverse" in self.obj.rawinput
        self.assertTrue(column_added)
        # check if column contains True and False
        self.assertEqual(self.obj.rawinput.Reverse.dtype, "bool")

    def test_standardize_protein_group_column(self):
        # check if column ProteinGroup has been added
        column_added = "ProteinGroup" in self.obj.rawinput
        self.assertTrue(column_added)

        # test function with different entries
        entry_one = "sp|P0DMV9|HS71B_HUMAN,sp|P0DMV8|HS71A_HUMAN"
        entry_one_protein_id = self.obj._standardize_protein_group_column(
            entry=entry_one
        )
        self.assertEqual(entry_one_protein_id, "P0DMV9;P0DMV8")

        entry_two = "ENSEMBL:ENSBTAP00000007350"
        entry_two_protein_id = self.obj._standardize_protein_group_column(
            entry=entry_two
        )
        self.assertEqual(entry_two_protein_id, "ENSBTAP00000007350")


class TestMaxQuantLoader(BaseTestLoader.BaseTest):
    def setUp(self):
        self.obj = MaxQuantLoader(file="testfiles/maxquant/proteinGroups.txt")
        self.df_dim = (2611, 2531)

    def test_set_filter_columns_to_true_false(self):
        # check if + has been replaced by TRUE FALSE
        self.assertEqual(self.obj.rawinput["Reverse"].dtype, "bool")
        self.assertEqual(self.obj.rawinput["Only identified by site"].dtype, "bool")
        self.assertEqual(self.obj.rawinput["Potential contaminant"].dtype, "bool")


class TestDIANNLoader(BaseTestLoader.BaseTest):
    def setUp(self):
        self.obj = DIANNLoader(file="testfiles/diann/report_final.pg_matrix.tsv")
        self.df_dim = (10, 26)

    def add_tag_to_sample_columns(self):
        # get number of columns that have tag
        n_taged_samples = len(
            self.obj.rawinput.filter(like="_Intensity").columns.to_list()
        )
        self.assertEqual(n_taged_samples, 20)

    def test_load_protein_data_df(self):
        df = pd.read_csv("testfiles/diann/report_final.pg_matrix.tsv", sep="\t")
        obj = DIANNLoader(df)
        self.assertIsInstance(obj.rawinput, pd.DataFrame)
        self.assertFalse(obj.rawinput.empty)

    def test_remove_filepath_windows(self):
        column_list = [
            "D:\\user\\path\\raw_A.d",
            "D:\\user\\path\\raw_B.d",
            "D:\\user\\path\\raw_C.d",
            "D:\\user\\path\\raw_D.d",
            "D:\\user\\path\\raw_F.d",
        ]
        expected_names = ["raw_A.d", "raw_B.d", "raw_C.d", "raw_D.d", "raw_F.d"]
        data = [[1, 2, 3, 4, 5], [1, 2, 3, 4, 5]]

        df = pd.DataFrame(data, columns=column_list)
        self.obj.rawinput = df
        self.obj._remove_filepath_from_name()
        self.assertEqual(self.obj.rawinput.columns.to_list(), expected_names)

    def test_remove_filepath_unix(self):
        column_list = [
            "path/to/file/raw_A.d",
            "path/to/file/raw_B.d",
            "path/to/file/raw_C.d",
            "path/to/file/raw_D.d",
            "path/to/file/raw_F.d",
        ]
        expected_names = ["raw_A.d", "raw_B.d", "raw_C.d", "raw_D.d", "raw_F.d"]
        data = [[1, 2, 3, 4, 5], [1, 2, 3, 4, 5]]

        df = pd.DataFrame(data, columns=column_list)
        self.obj.rawinput = df
        self.obj._remove_filepath_from_name()
        self.assertEqual(self.obj.rawinput.columns.to_list(), expected_names)


class TestFragPipeLoader(BaseTestLoader.BaseTest):
    def setUp(self):
        self.obj = FragPipeLoader(file="testfiles/fragpipe/combined_proteins.tsv")
        self.df_dim = (10, 37)


if __name__ == "__main__":
    unittest.main()
