"""The HoloNet window: browse, share and manage builds on zcom.app.

A window over the Den, under the editor menu bar (approved mockup boards
"In-game · Browse" and "In-game · Share a composition"). Its top-left corner
matches the library panels beside the tab rail; it stretches with the screen and
is 1640 wide at 1080p. Widget names the host already used for the Community panel
are kept, so its logic carries over.
"""
import ui_templates as e

PATH = e.ROOT + 'WBP_DenHolonet'
# The right margin that makes the window 1640 wide on a 1920-wide screen.
RIGHT = 1920 - e.LIBRARY_LEFT - 1640
RAIL, DETAIL, FORM = 232, 400, 560
GREEN = e.slate(0.33, 0.57, 0.15)
CARD_W, CARD_H = 238, 250
SOURCE_W = 266
# Rail entries: (widget, label, event, icon). The runtime marks the current area.
RAIL_BROWSE = [('RailCompositions', 'Compositions', 'community_browse', 'compositions'),
               ('RailDens', 'Dens', 'community_browse_dens', 'layouts')]
RAIL_YOURS = [('RailShare', 'Share a build', 'community_upload', 'save'),
              ('RailShares', 'My Shares', 'holonet_shares', 'storeroom'),
              ('RailAccount', 'Account', 'community_account', 'settings')]
AREAS = [('BrowseArea', 'browse'), ('BrowseDenArea', 'browse_dens'), ('UploadArea', 'upload'),
         ('SharesArea', 'shares'), ('AccountArea', 'account')]


def fill(widget, padding=None):
    if isinstance(padding, dict):
        padding = padding['Padding']
    widget['slot'] = dict(widget.get('slot', {}), Size='(SizeRule=Fill,Value=1)', **({'Padding': padding} if padding else {}))
    return widget


def sized(name, child, width=None, height=None, slot=None):
    props = {}
    if width:
        props.update(WidthOverride=width, bOverride_WidthOverride='true')
    if height:
        props.update(HeightOverride=height, bOverride_HeightOverride='true')
    box = {'class': '/Script/UMG.SizeBox', 'name': name, 'props': props, 'children': [child]}
    if slot:
        box['slot'] = slot
    return box


def vbox(name, children, slot=None, variable=False, visible=True):
    box = {'class': '/Script/UMG.VerticalBox', 'name': name, 'children': children}
    if slot:
        box['slot'] = slot
    if variable:
        box['variable'] = True
        box['props'] = {'Visibility': 'Visible' if visible else 'Collapsed'}
    return box


def hbox(name, children, slot=None):
    box = {'class': '/Script/UMG.HorizontalBox', 'name': name, 'children': children}
    if slot:
        box['slot'] = slot
    return box


def spacer(name):
    return {'class': '/Script/UMG.Spacer', 'name': name, 'slot': {'Size': '(SizeRule=Fill,Value=1)'}}


def panel(name, children, fill_color=e.rgba(1, 1, 1, 0.04), edge=e.EDGE, padding='(Left=14,Top=12,Right=14,Bottom=12)', variable=False, slot=None):
    border = {'class': '/Script/UMG.Border', 'name': name, 'props': e.surface(fill_color, edge, 8, padding),
              'children': [vbox(name + 'Column', children)]}
    if variable:
        border['variable'] = True
    if slot:
        border['slot'] = slot
    return border


def gap(top=0, bottom=8):
    return {'Padding': f'(Left=0,Top={top},Right=0,Bottom={bottom})'}


def primary(name, label, size=15):
    return e.button(name, label, size, 'primary')


def area(name, children, visible=False, horizontal=False):
    box = (hbox if horizontal else vbox)(name, children, slot={'Size': '(SizeRule=Fill,Value=1)'})
    box['variable'] = True
    box['props'] = {'Visibility': 'Visible' if visible else 'Collapsed'}
    return box


def tiles(name, width, entry_width, entry_height=CARD_H):
    view = e.cards(name)
    view['props'].update(EntryWidth=entry_width, EntryHeight=entry_height)
    return view


def title_bar():
    close = e.button('CommunityClose', 'Close', 14, 'ghost', color=e.SOFT)
    pill = {'class': '/Script/UMG.Border', 'name': 'ConnectionPill', 'props': e.surface(e.rgba(1, 1, 1, 0.06), None, 17, '(Left=12,Top=6,Right=14,Bottom=6)'),
            'slot': {'VerticalAlignment': 'VAlign_Center', 'Padding': '(Left=0,Top=0,Right=10,Bottom=0)'},
            'children': [e.text('ConnectionLabel', 'Not connected', 14, e.SOFT)]}
    return {'class': '/Script/UMG.Border', 'name': 'TitleBar', 'props': e.surface(e.rgba(0, 0, 0, 0.25), None, 0, '(Left=20,Top=10,Right=12,Bottom=10)'),
            'children': [hbox('TitleRow', [
                e.image('HolonetMark', 'community', 24, e.ACCENT, {'VerticalAlignment': 'VAlign_Center', 'Padding': '(Left=0,Top=0,Right=12,Bottom=0)'}),
                e.text('HolonetTitle', 'HOLONET', 20, e.GOLD, role='title', slot={'VerticalAlignment': 'VAlign_Center', 'Padding': '(Left=0,Top=0,Right=14,Bottom=0)'}),
                e.text('HolonetSubtitle', 'Builds shared by other captains', 15, e.SOFT, slot={'VerticalAlignment': 'VAlign_Center'}),
                spacer('TitleSpace'), pill, close])]}


def rail_entry(name, label, icon):
    """A rail toggle with its icon and caption on the left, so every entry lines up."""
    entry = e.toggle(name, label, icon)
    entry['children'][0]['children'][0]['slot']['HorizontalAlignment'] = 'HAlign_Left'
    return entry


def rail():
    # Hints sit under their entry's caption: button padding 10 + icon 20 + gap 7.
    hint = {'Padding': '(Left=37,Top=0,Right=0,Bottom=4)'}
    entries = [e.label('RailBrowseLabel', 'Browse', slot=gap(6, 8))]
    entries += [rail_entry(n, l, i) for n, l, _, i in RAIL_BROWSE]
    entries.append(e.text('RailDensSoon', 'Coming soon', 11, e.DIM, slot=hint))
    entries.append(e.label('RailYoursLabel', 'Yours', slot=gap(18, 8)))
    entries += [rail_entry(n, l, i) for n, l, _, i in RAIL_YOURS]
    entries.append(e.text('SharesCount', '', 12, e.DIM, slot=hint))
    entries.append(spacer('RailSpace'))
    code = e.box('CommunityCode', 'Code or zcom.app link', select_all=True)
    entries.append(panel('CodeBox', [
        e.label('CodeLabel', 'Have a code?', 13, e.GOLD, slot=gap(0, 8)),
        dict(code, slot=gap(0, 8)), primary('FetchCommunity', 'Import'),
        e.text('CodeHint', 'Codes or zcom.app links both work.', 12, e.DIM, wrap=True)],
        e.rgba(*e.ACCENT, 0.07), e.rgba(*e.ACCENT, 0.3)))
    column = vbox('RailColumn', entries)
    return sized('Rail', {'class': '/Script/UMG.Border', 'name': 'RailFrame', 'props': e.surface(e.rgba(0, 0, 0, 0.15), None, 0, '(Left=12,Top=16,Right=12,Bottom=16)'),
                          'children': [column]}, width=RAIL)


def chips():
    return hbox('SortRow', [e.toggle('SortNewest', 'Newest', 'catalog'), e.toggle('SortImports', 'Most imported', 'store'),
                            spacer('SortSpace'), e.toggle('FilterUsable', 'Only what I can use', 'done')], slot=gap(8, 6))


def browse():
    search = e.entry_row('SearchRow', e.box('CommunitySearch', 'Search titles and creators'), e.button('SearchCommunity', 'Search', 14))
    gallery = vbox('Gallery', [
        search, chips(),
        e.text('BrowseStatus', 'Hides builds that need prop packs you don’t have installed.', 13, e.DIM, wrap=True),
        tiles('CommunityListings', 0, CARD_W),
        hbox('PageRow', [e.button('PreviousCommunity', 'Previous', 14), e.text('GalleryStatus', 'Loading builds…', 14, e.SOFT, slot={'VerticalAlignment': 'VAlign_Center', 'Size': '(SizeRule=Fill,Value=1)', 'Padding': '(Left=8,Top=0,Right=8,Bottom=6)'}),
                         e.button('NextCommunity', 'Next', 14), e.button('RefreshCommunity', 'Refresh', 14, 'ghost')], slot=gap(4, 0))],
        slot={'Size': '(SizeRule=Fill,Value=1)', 'Padding': '(Left=20,Top=18,Right=20,Bottom=12)'})
    picture = sized('DetailPictureSize', {'class': '/Script/UMG.Overlay', 'name': 'DetailPictureLayers', 'children': [
        {'class': '/Script/UMG.Border', 'name': 'DetailPictureBack', 'props': e.surface(e.rgba(0.004, 0.005, 0.006), None, 6, '(Left=0,Top=0,Right=0,Bottom=0)'),
         'slot': {'HorizontalAlignment': 'HAlign_Fill', 'VerticalAlignment': 'VAlign_Fill'}},
        {'class': '/Script/UMG.Image', 'name': 'CommunityPreview', 'variable': True, 'props': {'Visibility': 'Hidden', 'Brush.ImageSize': '(X=250,Y=250)'},
         'slot': {'HorizontalAlignment': 'HAlign_Center', 'VerticalAlignment': 'VAlign_Center'}}]}, width=DETAIL - 40, height=250, slot=gap(0, 12))
    facts = vbox('Facts', [hbox('Fact' + name, [e.text('Fact' + name + 'Label', label, 15, e.SOFT, slot={'Size': '(SizeRule=Fill,Value=1)'}), e.text('Fact' + name + 'Value', '', 15, e.GOLD if name == 'Code' else e.WHITE)], slot=gap(4, 4))
                           for name, label in [('Parts', 'Parts'), ('Footprint', 'Footprint'), ('Code', 'Code')]], slot=gap(4, 8))
    ready = panel('DetailReady', [e.text('DetailReadyText', '', 15, e.WHITE, wrap=True), e.button('GetPack', 'Get the prop pack on Nexus', 13, 'outline')],
                  e.rgba(0.33, 0.57, 0.15, 0.10), e.rgba(0.33, 0.57, 0.15, 0.35), '(Left=12,Top=10,Right=12,Bottom=10)', variable=True, slot=gap(0, 8))
    detail = sized('Detail', {'class': '/Script/UMG.Border', 'name': 'DetailFrame', 'props': e.surface(e.rgba(0, 0, 0, 0.12), None, 0, '(Left=20,Top=18,Right=20,Bottom=18)'),
                              'children': [vbox('DetailColumn', [
                                  picture,
                                  e.text('DetailTitle', 'Select a build', 24, e.GOLD, role='heading', wrap=True),
                                  e.text('DetailByline', '', 15, e.SOFT, wrap=True, slot=gap(4, 10)),
                                  fill(sized('DetailSize', {'class': '/Script/UMG.ScrollBox', 'name': 'DetailScroll', 'props': {},
                                                            'children': [e.text('CommunityDetail', 'Pick a card to see what it is, who made it and what it needs.', 15, e.SOFT, wrap=True)]}, height=120), gap(0, 10)),
                                  ready, facts,
                                  dict(primary('DownloadCommunity', 'Add to my Compositions'), slot=gap(0, 8)),
                                  e.button('PlaceCommunity', 'Add and place now', 15, 'outline')])]}, width=DETAIL)
    return area('BrowseArea', [gallery, detail], visible=True, horizontal=True)


def share():
    picker = vbox('SharePicker', [
        e.label('ShareStepOne', '1 · Pick what to share', 13, e.WHITE, slot=gap(0, 4)),
        e.text('UploadSelection', 'Choose a saved composition. Den layouts: coming soon.', 13, e.DIM, wrap=True),
        tiles('CommunitySources', 0, SOURCE_W)],
        slot={'Size': '(SizeRule=Fill,Value=1)', 'Padding': '(Left=20,Top=18,Right=20,Bottom=12)'})
    choice = vbox('ShareChoice', [
        e.label('ShareChoiceLabel', 'This share', slot=gap(6, 6)),
        e.toggle('ShareUpdate', 'Update an existing share', 'save', fill=False),
        e.toggle('ShareNew', 'Share as a new build with a new code', 'catalog', fill=False)])
    changelog = vbox('ChangelogBox', [
        e.label('ChangelogLabel', 'What changed', slot=gap(10, 6)),
        e.box('PublishChangelog', 'What changed in this revision (up to 500 characters)'),
        e.text('ChangelogHint', 'Shown in the changelog on the build’s HoloNet page. Only asked when updating.', 13, e.DIM, wrap=True, slot=gap(4, 0))],
        variable=True, visible=False)
    offline = panel('ShareOffline', [
        e.text('ShareOfflineTitle', 'Connect your account first', 18, e.WHITE, role='heading'),
        e.text('ShareOfflineText', 'Sign in with Steam at zcom.app/account, make a game key, and paste it in Account. You only do this once per PC.', 15, e.SOFT, wrap=True, slot=gap(6, 10)),
        primary('ShareGoAccount', 'Go to Account')], e.rgba(*e.ACCENT, 0.07), e.rgba(*e.ACCENT, 0.35), variable=True)
    offline['props']['Visibility'] = 'Collapsed'
    result = panel('ShareResult', [
        e.text('ShareResultTitle', 'Shared', 18, e.WHITE, role='heading'),
        e.label('ShareResultCodeLabel', 'Code', slot=gap(10, 4)),
        e.text('ShareResultCode', '', 46, e.GOLD, role='title'),
        e.text('PublishResult', '', 15, e.SOFT, wrap=True, slot=gap(4, 10)),
        hbox('CopyResult', [fill(primary('CopyCommunityCode', 'Copy code')), fill(e.button('CopyCommunityURL', 'Copy link', 15, 'outline'))])],
        e.rgba(*e.ACCENT, 0.07), e.rgba(*e.ACCENT, 0.45), variable=True)
    result['props']['Visibility'] = 'Collapsed'
    form = vbox('ShareFormFields', [
        e.label('TitleLabel', 'Title', slot=gap(10, 6)), e.box('PublishTitle', 'Title (up to 120 characters)'),
        e.label('DescriptionLabel', 'Description (optional)', slot=gap(10, 6)), e.box('PublishDescription', 'What it is, where it fits (up to 4000 characters)'),
        choice, changelog], variable=True)
    footer = vbox('ShareFooter', [
        fill(sized('RequirementsSize', {'class': '/Script/UMG.ScrollBox', 'name': 'RequirementsScroll', 'props': {},
                                        'children': [e.text('PublishRequirements', '', 14, e.SOFT, wrap=True)]}, height=72), gap(8, 6)),
        e.text('ShareNote', 'Shares the saved copy of this composition, not your unsaved edits.', 14, e.DIM, wrap=True, slot=gap(0, 8)),
        hbox('ShareActions', [fill(primary('SubmitCommunity', 'Share', 17)), e.button('CancelCommunity', 'Cancel', 15, 'outline')])], variable=True)
    side = sized('ShareSide', {'class': '/Script/UMG.Border', 'name': 'ShareFrame', 'props': e.surface(e.rgba(0, 0, 0, 0.12), None, 0, '(Left=22,Top=18,Right=22,Bottom=18)'),
                               'children': [vbox('ShareColumn', [
                                   e.label('ShareStepTwo', '2 · Describe it', 13, e.WHITE, slot=gap(0, 6)),
                                   e.text('ShareSummary', 'Pick a composition on the left.', 15, e.SOFT, wrap=True),
                                   offline, result, form, spacer('ShareSpace'), footer])]}, width=FORM)
    return area('UploadArea', [picker, side], horizontal=True)


def shares():
    rows = {'class': '/Script/UMG.ListView', 'name': 'ShareListings', 'variable': True,
            'props': {'bIsFocusable': 'false', 'SelectionMode': 'Single', 'EntryWidgetClass': e.ROOT + 'WBP_DenCatalogShelf', **e.scrollbar()},
            'slot': {'Size': '(SizeRule=Fill,Value=1)', 'Padding': '(Left=0,Top=8,Right=0,Bottom=8)'}}
    column = vbox('SharesColumn', [
        e.text('SharesTitle', 'My Shares', 22, e.GOLD, role='heading'),
        e.text('SharesStatus', 'Connect in Account to see your shares.', 15, e.SOFT, wrap=True, slot=gap(6, 0)),
        rows,
        hbox('SharesPageRow', [e.button('SharesPrevious', 'Previous', 14), e.button('SharesNext', 'Next', 14), e.button('SharesRefresh', 'Refresh', 14, 'ghost'),
                               e.text('SharesHint', 'Pick one to share an update. Hide or show shares on zcom.app.', 13, e.DIM, wrap=True, slot={'VerticalAlignment': 'VAlign_Center', 'Padding': '(Left=10,Top=0,Right=0,Bottom=6)'})])],
        slot={'Size': '(SizeRule=Fill,Value=1)', 'Padding': '(Left=24,Top=20,Right=24,Bottom=16)'})
    return area('SharesArea', [column])


def account():
    key = e.box('CommunityKey', 'Game key from zcom.app/account (leave empty to reconnect)')
    key['props']['IsPassword'] = 'true'
    column = vbox('AccountColumn', [
        e.text('AccountTitle', 'Account', 22, e.GOLD, role='heading'),
        e.text('CommunityProfile', 'Not connected.', 15, e.SOFT, wrap=True, slot=gap(6, 10)),
        e.entry_row('CommunityKeyRow', key, primary('ConnectCommunity', 'Connect')),
        hbox('AccountActions', [e.button('RememberCommunity', 'Remember on this PC: Off', 14), e.button('DisconnectCommunity', 'Disconnect', 14), e.button('ForgetCommunity', 'Forget', 14)], slot=gap(6, 6)),
        e.text('CommunitySecurity', 'Remember on this PC saves the game key on this computer as plain text: anyone with that file can use it. Leave it off to stay connected for this session only; Forget removes the saved key. The key field clears when you connect or close.', 13, e.DIM, wrap=True, slot=gap(4, 12)),
        e.button('CommunityWebsite', 'Get a key at zcom.app/account', 14, 'outline')],
        slot={'Padding': '(Left=24,Top=20,Right=24,Bottom=16)'})
    return area('AccountArea', [sized('AccountWidth', column, width=760, slot={'HorizontalAlignment': 'HAlign_Left', 'Size': '(SizeRule=Fill,Value=1)'})])


def dens():
    return area('BrowseDenArea', [vbox('DensColumn', [
        e.text('DensTitle', 'Dens', 22, e.GOLD, role='heading'),
        e.text('DensSoon', 'Sharing whole Den layouts is coming soon. For now, share and import compositions.', 15, e.SOFT, wrap=True, slot=gap(6, 0))],
        slot={'Padding': '(Left=24,Top=20,Right=24,Bottom=16)'})])


def tree():
    body = hbox('Body', [rail(), browse(), dens(), share(), shares(), account()], slot={'Size': '(SizeRule=Fill,Value=1)'})
    # 'Panel': the host blocks world clicks while the pointer is over a panel.
    window = {'class': '/Script/UMG.Border', 'name': 'Panel', 'variable': True,
              'props': dict(e.surface(e.rgba(0.0027, 0.003, 0.004, 0.94), e.rgba(*e.ACCENT, 0.3), 10, '(Left=0,Top=0,Right=0,Bottom=0)'), Clipping='ClipToBounds'),
              'slot': {'LayoutData': f'(Offsets=(Left={e.LIBRARY_LEFT},Top=80,Right={RIGHT},Bottom=58),Anchors=(Minimum=(X=0,Y=0),Maximum=(X=1,Y=1)))'},
              'children': [vbox('WindowColumn', [
                  title_bar(), body,
                  e.text('Footer', '', 13, e.DIM, wrap=True, slot={'Padding': '(Left=20,Top=6,Right=20,Bottom=10)'})])]}
    return {'class': '/Script/UMG.CanvasPanel', 'name': 'Root', 'children': [window]}


def commit_on_enter(g, box, event):
    """Native_Event(event, text) on Enter only; losing focus doesn't search again."""
    g.commit(box, event)
    g.links.remove([box + '.then', box + '_event.execute'])
    g.nodes += [dict(id=box + '_enter', kind='call', function='/Script/Engine.KismetMathLibrary:EqualEqual_ByteByte', defaults={'B': '1'}),
                dict(id=box + '_entered', kind='branch')]
    g.links += [[box + '.CommitMethod', box + '_enter.A'], [box + '_enter.ReturnValue', box + '_entered.Condition'],
                [box + '.then', box + '_entered.execute'], [box + '_entered.then', box + '_event.execute']]


def spec():
    g = e.Graph()
    for name, _, event, _ in RAIL_BROWSE + RAIL_YOURS:
        g.click(name, event)
    for button, event in [('CommunityClose', 'community_close'), ('SortNewest', 'holonet_sort_newest'), ('SortImports', 'holonet_sort_imports'),
                          ('FilterUsable', 'holonet_usable'), ('PreviousCommunity', 'community_previous'), ('NextCommunity', 'community_next'),
                          ('RefreshCommunity', 'community_refresh'), ('DownloadCommunity', 'community_download'), ('PlaceCommunity', 'holonet_place'),
                          ('GetPack', 'holonet_get_pack'), ('ShareUpdate', 'holonet_share_update'), ('ShareNew', 'holonet_share_new'),
                          ('ShareGoAccount', 'community_account'), ('SubmitCommunity', 'community_submit'), ('CancelCommunity', 'community_cancel'),
                          ('CopyCommunityCode', 'community_copy_code'), ('CopyCommunityURL', 'community_copy_url'), ('SharesPrevious', 'holonet_shares_previous'),
                          ('SharesNext', 'holonet_shares_next'), ('SharesRefresh', 'holonet_shares_reload'), ('ConnectCommunity', 'community_connect'),
                          ('RememberCommunity', 'community_remember'), ('DisconnectCommunity', 'community_disconnect'), ('ForgetCommunity', 'community_forget'),
                          ('CommunityWebsite', 'community_website')]:
        g.click(button, event)
    g.click_with_text('FetchCommunity', 'community_fetch', 'CommunityCode')
    g.click_with_text('SearchCommunity', 'community_search', 'CommunitySearch')
    commit_on_enter(g, 'CommunitySearch', 'community_search')
    g.item('CommunityListings', 'community_listing')
    g.item('CommunitySources', 'holonet_pick_source')
    g.item('ShareListings', 'holonet_pick_share')
    return {'kind': 'widget', 'path': PATH, 'tree': tree(), 'functions': e.NATIVE_EVENT, 'graph': g.spec()}
