"""Composition browser, authored only for the pak edition."""
import ui_templates as e


def spec():
    g=e.Graph()
    tree=e.library_panel('Compositions',[
        e.text('SelectionCount','0 parts selected',16,e.GOLD,role='heading'),
        e.text('SelectionHint','Select parts, then click each prop to add or remove it. Save a reusable copy of the arrangement; originals stay in place.',12,e.DIM,wrap=True),
        e.row('SelectionRow',[e.button('SelectParts','Select parts',14),e.button('ClearParts','Clear selection',14)]),
        e.entry_row('SaveRow',e.box('CompositionName','Composition name'),e.button('SaveComposition','Save',14)),
        e.divider('LibraryDivider',vertical=False),
        e.label('LibraryTitle','Saved compositions'),
        e.cards('Compositions'),
        e.row('LibraryRow',[e.button('LoadComposition','Place selected',14),e.button('ShareComposition','Share',14),e.button('DeleteComposition','Delete selected',14)]),
        e.text('Footer','',12,e.DIM,wrap=True),
    ])
    g.click('ClosePanel','library_close');g.click('SelectParts','composition_select');g.click('ClearParts','composition_clear')
    g.click_with_text('SaveComposition','save_composition','CompositionName');g.commit('CompositionName','save_composition')
    # Focus loss must not save again after Enter or before the Save button click.
    g.links.remove(['CompositionName.then','CompositionName_event.execute'])
    g.nodes += [dict(id='name_enter',kind='call',function='/Script/Engine.KismetMathLibrary:EqualEqual_ByteByte',defaults={'B':'1'}),dict(id='name_entered',kind='branch')]
    g.links += [['CompositionName.CommitMethod','name_enter.A'],['name_enter.ReturnValue','name_entered.Condition'],['CompositionName.then','name_entered.execute'],['name_entered.then','CompositionName_event.execute']]
    g.item('Compositions','composition_card');g.click('LoadComposition','load_composition');g.click('ShareComposition','holonet_share_selected');g.click('DeleteComposition','delete_composition')
    return {'kind':'widget','path':e.ROOT+'WBP_DenCompositions','tree':tree,'functions':e.NATIVE_EVENT,'graph':g.spec()}
