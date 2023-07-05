from random import gauss
import numpy
from root_numpy import root2array, list_trees, list_branches
from rootpy.io import root_open
from rootpy.tree import Tree, TreeModel
from rootpy.types import FloatCol, Char, IntCol, CharCol, CharArrayCol


class ROOTHelpers(object):
    def export_root_data_contents(self, rfile):
        """
        Uses the root_numpy class to list trees and output them.
        :param rfile: Input ROOT file
        :return: a dictionary defining the underlying data in the file link. The key is the name of each tree.
        """
        for tree in list_trees(rfile):
            print 'Processing tree ' + tree
            print list_branches(rfile, tree)
            arr = root2array(rfile, treename=tree)
            print str(arr.view(numpy.recarray))

    def add_tree_to_file(self, file_name, table_name, table_title, headers, data, mode="update"):
        """
        :param table_name
        :param table_title
        :param headers: should be a dictionary defining each column name and it's data type.
                        Valid data types are Floats (F) and Integers (I).
                        So to define a simple X, Y plot where X is an Integer and Y is a Float,
                        we'd define {'X': 'I', 'Y': 'F'}
        :param data: defined as an array of dictionary objects defining the values for each record.
                    For example, X and Y in the above case would be [{'X':0,'Y':23.12}, {'X':1,'Y':20.12}, ...]
        """

        f = root_open(file_name, mode)

        new_tree = Tree(name=table_name, title=table_title)
        new_tree.create_branches(headers)

        for record in data:
            for key, value in record.iteritems():
                new_tree[key] = value
            new_tree.fill()

        new_tree.write()

        f.close()


class MetaDataRecord(TreeModel):
    value = CharCol()


class DataValue(TreeModel):
    """
        For each value, we have its error on the X and Y axes
    """
    val = FloatCol()

    err_label = CharArrayCol()
    err_minus = FloatCol()
    err_plus = FloatCol()



class DataRecord(DataValue.prefix('x_'), DataValue.prefix('y_expected_'), DataValue.prefix('y_observed_')):
    i = IntCol()


class DataGenerator(object):

    def generate_root_file_with_tree(self, file_name, mode="update"):
        f = root_open(file_name, mode)

        # how can we capture the qualifier information? It seems wasteful to have to duplicate it...
        tree_meta = Tree(name="Table 1::metadata", title="Table 1", model=DataRecord)
        tree_meta.create_branches(
            {'reaction': 'C',
             'qualifier_1_type': 'C',
             'qualifier_1_value': 'C',
             'qualifier_2_type': 'C',
             'qualifier_2_value': 'C'}
        )

        tree_meta.reaction = 'P --> P'
        tree_meta.qualifier_1_type = 'SQRT(S)'
        tree_meta.qualifier_1_value = '8000.0 GeV'
        tree_meta.qualifier_1_type = ''
        tree_meta.qualifier_1_value = '95% CL Limit'

        tree_meta.fill()

        tree = Tree(name="Table 1::data", title="Table 1", model=DataRecord)
        # F - Float, I - Integer


        for i in xrange(1000):
            tree.qual_1_type = "sqrt(s)"
            tree.qual_1_value = "8000.0 GeV"

            tree.qual_2_type = ""
            tree.qual_2_value = "95% CL upper limit [fb]"

            tree.x_val = gauss(1., 4.)
            tree.x_err_y_minus = gauss(0., 1)
            tree.x_err_y_plus = gauss(0., 1)

            tree.expected_val = gauss(1., 4.)
            tree.expected_err_y_minus = gauss(1., 4.)
            tree.expected_err_x_minus = gauss(1., 4.)

            tree.observed_val = gauss(1., 4.)
            tree.observed_err_y_minus = gauss(1., 4.)
            tree.observed_err_x_minus = gauss(1., 4.)

            tree.i = i
            tree.fill()

        tree.write()

        f.close()


if __name__ == "__main__":
    rh = ROOTHelpers()
    dg = DataGenerator()

    dg.generate_root_file_with_tree('/Users/eamonnmaguire/git/CERN/root_data_extractor/data/hsimple.root',
                                    mode="update")
    rh.export_root_data_contents('/Users/eamonnmaguire/git/CERN/root_data_extractor/data/hsimple.root')
