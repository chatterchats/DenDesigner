"""The standalone catalog converter preserves the published catalog identities."""
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/build'))
from build_catalog import metadata, name_of


class CatalogDataTests(unittest.TestCase):
    def test_existing_rows_and_collection_membership_survive_conversion(self):
        source=json.loads((ROOT/'unreal/data/catalog.json').read_text())
        shelves={s['title']:[] for s in source['shelves']}
        for row in source['items']:
            shelves[source['shelves'][row['shelf']-1]['title']].append(
                (row['path'].rsplit('.',1)[-1],row['path'],row['size'],row['collision']))
        rebuilt=metadata(shelves)
        for field in ('items','shelves','collections'):
            self.assertEqual(rebuilt[field],source[field],field)

    def test_names_keep_materially_distinct_tokens(self):
        self.assertEqual(name_of('/Game/X.SM_UNI_CrateR8A_Small'),'Crate R8A Small')
        self.assertEqual(name_of('/Game/X.SM_REP_MedicalBed_A'),'REP Medical Bed A')

    def test_dimensions_collision_and_order(self):
        data=metadata({'Other: Widgets':[('SM_B','/Pack/SM_B.SM_B',[201,100,50],False)],
                       'Den: Bar':[('SM_A','/Game/SM_A.SM_A',[20,30,40],True)]})
        self.assertEqual(data['items'][0]['detail'],'20 x 30 x 40 cm')
        self.assertEqual(data['items'][1]['detail'],'2.0 x 1.0 x 0.5 m\nNo collision')
        self.assertEqual([c['key'] for c in data['collections']],['Den','Other'])
        self.assertEqual([s['first'] for s in data['shelves']],[1,2])

    def test_provenance_is_deterministic_and_changes_with_content(self):
        shelves={'Den: Bar':[('SM_A','/Game/SM_A.SM_A',[20,30,40],True)]}
        first=metadata(shelves)
        self.assertEqual(first,metadata(shelves))
        shelves['Den: Bar'][0]=('SM_A','/Game/SM_A.SM_A',[20,30,41],True)
        self.assertNotEqual(first['source_hash'],metadata(shelves)['source_hash'])


if __name__=='__main__':unittest.main()
