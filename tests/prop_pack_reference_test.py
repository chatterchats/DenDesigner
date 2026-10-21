"""The authoring dependency cannot replace a developer's existing plugin."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import prop_pack_reference as reference


class ReferenceTests(unittest.TestCase):
    def test_minimal_reference_and_refuse_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=root/'unreal/DenDesignerGF/Content/Runtime/BP_DenPropPack.uasset'
            source.parent.mkdir(parents=True);source.write_bytes(b'authored-provider')
            output=root/'kit/Plugins/DenDesignerGF'
            with patch.object(reference,'verify',return_value={'version':'0.9.0-preview.2'}):
                result=reference.export(output,root)
                self.assertTrue(result['editor_reference_only'])
                self.assertEqual((output/'Content/Runtime/BP_DenPropPack.uasset').read_bytes(),source.read_bytes())
                self.assertEqual(len(list((output/'Content').rglob('*.uasset'))),1)
                descriptor=json.loads((output/'DenDesignerGF.uplugin').read_text())
                self.assertFalse(descriptor['ExplicitlyLoaded'])
                self.assertNotIn('BuiltInInitialFeatureState',descriptor)
                with self.assertRaisesRegex(ValueError,'existing plugin'):reference.export(output,root)
                self.assertEqual((output/'Content/Runtime/BP_DenPropPack.uasset').read_bytes(),source.read_bytes())


if __name__=='__main__':unittest.main()
