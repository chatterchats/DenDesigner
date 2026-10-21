"""Shared/per-campaign routing through Blueprint, preserving kit fixture slots."""
import os
import uuid
from pathlib import Path


def run(unreal, root, source, fixture, check):
    saved=Path(unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_saved_dir())).resolve()
    assert saved == Path(os.environ['DENDESIGNER_TEST_SAVED']).resolve()
    manager=unreal.new_object(unreal.EditorAssetLibrary.load_blueprint_class(root+'BP_DenLayouts'))
    campaign=uuid.uuid4().hex.upper()
    key='campaign-'+campaign

    def slot(logical,bank,draft=False):
        return manager.call_method('BankSlot',(logical,bank,draft))

    def paths(logical,draft=False):
        return [saved/'SaveGames'/(slot(logical,i,draft)+'.sav') for i in range(2 if draft else 6)]

    touched=paths('home')+paths('home',True)+paths(key)+paths(key,True)
    assert all(p.is_relative_to(saved/'SaveGames/ZComDen/Native/v1') and not p.is_dir() for p in touched)
    originals={p:p.read_bytes() for p in touched if p.exists()}

    def bytes_for(logical,draft=False):
        return {p.name:p.read_bytes() for p in paths(logical,draft) if p.exists()}

    def prop(obj,name):
        return obj.get_editor_property(name)

    def resolve(cid):
        return manager.call_method('ResolveLayout',(cid,))

    try:
        for p in touched:
            p.unlink(missing_ok=True)
        doc,status,chosen,own,known=resolve('')
        check(doc is None and status == 0 and chosen == 'home' and not own and not known, 'unknown campaign resolves to shared home')
        check(not manager.call_method('CampaignKey',('not-a-guid',))[1] and
              not manager.call_method('CampaignKey',('G'*32,))[1] and
              not manager.call_method('CampaignKey',('0'*32,))[1], 'campaign IDs require 32 hex digits and a nonzero GUID')
        canonical,valid,cid=manager.call_method('CampaignKey',(campaign.lower(),))
        check(valid and canonical == key and cid == campaign, 'campaign ID normalizes to stable uppercase key')
        home=manager.call_method('CloneLayout',(source,))
        fixture.call_method('SetDisplayName',(home,'Shared home'))
        saved_home,status=manager.call_method('SaveLayout',('home',home,False,0,''))
        assert status == 1
        home_bytes=bytes_for('home')
        doc,status,chosen,own,known=resolve(campaign)
        check(status == 1 and chosen == 'home' and not own and known and prop(doc,'DisplayName') == 'Shared home', 'campaign without an override uses home')
        own_doc,status=manager.call_method('MakeCampaign',(campaign.lower(),doc))
        check(status == 1 and prop(own_doc,'Scope') == 'campaign' and prop(own_doc,'CampaignID') == campaign and prop(own_doc,'Enabled'), 'campaign copy gets correct scope and identity')
        check(bytes_for('home') == home_bytes and prop(doc,'Scope') == 'home', 'making a campaign copy preserves shared file and source object')
        doc,status,chosen,own,known=resolve(campaign)
        check(status == 1 and chosen == key and own and known, 'active override resolves to campaign layout')
        fixture.call_method('SetDisplayName',(doc,'Campaign edit'))
        own_doc,status=manager.call_method('SaveLayout',(key,doc,False,0,''))
        assert status == 1
        _,status=manager.call_method('SaveLayout',(key,doc,True,prop(own_doc,'Revision'),prop(own_doc,'ContentID')))
        assert status == 1
        draft_bytes=bytes_for(key,True)
        check(manager.call_method('UseHome',(campaign,)) == 1, 'returning to shared home succeeds')
        doc,status,chosen,own,known=resolve(campaign)
        check(status == 1 and chosen == 'home' and not own and prop(doc,'DisplayName') == 'Shared home', 'disabled campaign resolves back to shared home')
        retained,status,_=manager.call_method('LoadLayout',(key,False,0))
        check(status == 1 and not prop(retained,'Enabled') and prop(retained,'DisplayName') == 'Campaign edit', 'switching to home retains the edited campaign layout')
        previous,status,_=manager.call_method('LoadLayout',(key,False,prop(retained,'Revision')))
        check(status == 1 and prop(previous,'Enabled') and prop(previous,'DisplayName') == 'Campaign edit', 'prior enabled campaign version remains a backup')
        check(bytes_for(key,True) == draft_bytes and bytes_for('home') == home_bytes, 'switching scope preserves campaign draft and shared files')
        before=bytes_for(key)
        check(manager.call_method('UseHome',(campaign,)) == 1 and bytes_for(key) == before, 'switching an already disabled campaign is a no-op')
        reenabled,status=manager.call_method('MakeCampaign',(campaign,retained))
        check(status == 1 and prop(reenabled,'Enabled') and prop(resolve(campaign)[0],'DisplayName') == 'Campaign edit', 'retained campaign layout can be re-enabled')
        check(manager.call_method('UseHome',('invalid',)) == 7 and manager.call_method('MakeCampaign',('invalid',home))[1] == 7, 'invalid campaign operations are rejected')
        latest,_,bank=manager.call_method('LoadLayout',(key,False,0))
        fixture.call_method('SetSchemaVersion',(latest,2))
        assert unreal.GameplayStatics.save_game_to_slot(latest,slot(key,bank),0)
        _,status,chosen,own,_=resolve(campaign)
        check(status == 4 and chosen == key and own, 'newer campaign data does not silently redirect edits into home')
        check(manager.call_method('UseHome',(campaign,)) == 4 and bytes_for('home') == home_bytes, 'newer campaign data is preserved when switching fails')
    finally:
        for p in touched:
            if p in originals:
                p.parent.mkdir(parents=True,exist_ok=True)
                p.write_bytes(originals[p])
            else:
                p.unlink(missing_ok=True)
