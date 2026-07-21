import os
import unittest
import pandas as pd
from src.claims_analysis import load_data, build_loss_triangle, calculate_chainladder_factors, project_ultimate_and_ibnr

class TestClaimsReserving(unittest.TestCase):

    def setUp(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.dataset_path = os.path.join(base_dir, 'data', 'pc_claims_dataset.csv')

    def test_data_loading(self):
        df = load_data(self.dataset_path)
        self.assertFalse(df.empty)
        self.assertIn('line_of_business', df.columns)
        self.assertIn('paid_claims', df.columns)

    def test_loss_triangle_shape(self):
        df = load_data(self.dataset_path)
        triangle = build_loss_triangle(df, 'Commercial Property', 'paid_claims')
        self.assertFalse(triangle.empty)
        self.assertEqual(triangle.index.name, 'accident_year')
        self.assertEqual(triangle.columns.name, 'development_year')

    def test_chainladder_factors(self):
        df = load_data(self.dataset_path)
        triangle = build_loss_triangle(df, 'Commercial Property', 'paid_claims')
        ldfs, cdfs = calculate_chainladder_factors(triangle)
        self.assertEqual(len(ldfs), len(triangle.columns) - 1)
        self.assertTrue(all(f >= 1.0 for f in ldfs))
        self.assertEqual(cdfs[-1], 1.0)

    def test_reserving_projections(self):
        df = load_data(self.dataset_path)
        triangle = build_loss_triangle(df, 'Commercial Property', 'paid_claims')
        ldfs, cdfs = calculate_chainladder_factors(triangle)
        premium_map = df[df['line_of_business'] == 'Commercial Property'].groupby('accident_year')['earned_premium'].first().to_dict()
        
        res = project_ultimate_and_ibnr(triangle, cdfs, premium_map, initial_expected_loss_ratio=0.75)
        self.assertFalse(res.empty)
        self.assertIn('cl_ultimate_claims', res.columns)
        self.assertIn('bf_ultimate_claims', res.columns)
        self.assertTrue((res['cl_ibnr_reserve'] >= 0).all())

if __name__ == '__main__':
    unittest.main()
