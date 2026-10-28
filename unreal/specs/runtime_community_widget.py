"""Composition browser, authored only for the pak edition."""
import ui_templates as e


def spec():
    g=e.Graph()
    key=e.box('CommunityKey','Game upload key (leave blank to reconnect)');key['props']['IsPassword']='true'
    def area(name, children, visible=False):
        return {'class':'/Script/UMG.VerticalBox','name':name,'variable':True,'props':{'Visibility':'Visible' if visible else 'Collapsed'},'slot':{'Size':'(SizeRule=Fill,Value=1)'} if name=='BrowseArea' else {},'children':children}
    tree=e.library_panel('Community',[
        e.row('CommunityTabs',[e.button('CommunityBrowse','Browse',14),e.button('CommunityUpload','Upload',14),e.button('CommunityAccount','Account',14),e.button('CommunityClose','Close',14)]),
        area('BrowseArea',[
            e.row('BrowseKinds',[e.button('BrowseCompositions','Compositions',14),e.button('BrowseDens','Dens',14)]),
            e.text('BrowseStatus','Public compositions. Previews are rendered locally from validated part information. Import by code/link is also available.',12,e.DIM,wrap=True),
            e.entry_row('CommunityRow',e.box('CommunityCode','Composition code or zcom.app link'),e.button('FetchCommunity','Import',14)),
            e.entry_row('SearchRow',e.box('CommunitySearch','Search public compositions'),e.button('SearchCommunity','Search',14)),
            e.row('PageRow',[e.button('PreviousCommunity','Previous',14),e.button('NextCommunity','Next',14),e.button('RefreshCommunity','Refresh',14)]),
            e.text('GalleryStatus','Choose Refresh to load public compositions.',12,e.DIM,wrap=True),
            e.cards('CommunityListings'),
            e.row('DetailRow',[{'class':'/Script/UMG.SizeBox','name':'DetailPictureSize','props':{'WidthOverride':'128','HeightOverride':'128','bOverride_WidthOverride':'true','bOverride_HeightOverride':'true'},'children':[{'class':'/Script/UMG.Image','name':'CommunityPreview','variable':True,'props':{'Visibility':'Hidden'}}]}, {'class':'/Script/UMG.SizeBox','name':'DetailSize','slot':{'Size':'(SizeRule=Fill,Value=1)'},'props':{'HeightOverride':'150','bOverride_HeightOverride':'true'},'children':[{'class':'/Script/UMG.ScrollBox','name':'DetailScroll','children':[e.text('CommunityDetail','Select a public composition to inspect its description, requirements and revision.',12,e.DIM,wrap=True)]}]}]),
            e.button('DownloadCommunity','Download to local Compositions',14),
        ],True),
        area('UploadArea',[
            e.row('UploadKinds',[e.button('UploadComposition','Composition',14),e.button('UploadDen','Full Den',14)]),
            e.text('UploadSelection','Choose a saved composition card below, then Review saved snapshot.',12,e.DIM,wrap=True),
            e.button('ReviewCommunity','Review saved snapshot',14),
            e.box('PublishTitle','Title (1–120 printable ASCII characters)'),
            e.box('PublishDescription','Description (up to 4000 printable ASCII characters)'),
            e.text('UpdateHint','Create new: leave both fields empty. Update yours: share code and current revision.',12,e.DIM,wrap=True),
            e.entry_row('UpdateRow',e.box('PublishCode','Existing share code (optional)'),e.box('PublishRevision','Current revision')),
            {'class':'/Script/UMG.SizeBox','name':'RequirementsSize','props':{'HeightOverride':'110','bOverride_HeightOverride':'true'},'children':[{'class':'/Script/UMG.ScrollBox','name':'RequirementsScroll','props':{},'children':[e.text('PublishRequirements','Review a saved snapshot to see all mesh and material dependencies. Pack ownership is unknown until service validation.',12,e.DIM,wrap=True)]}]},
            e.button('SubmitCommunity','Publish / retry reviewed snapshot',14),
            e.text('PublishResult','',12,e.GOLD,wrap=True),
            e.row('CopyResult',[e.button('CopyCommunityURL','Copy public URL',14),e.button('CopyCommunityCode','Copy share code',14)]),
        ]),
        area('BrowseDenArea',[e.text('BrowseDenPlaceholder','Dens sharing is not implemented yet. Public Den browsing and downloading will become available when the Den service and capture stage are ready.',12,e.DIM,wrap=True)]),
        area('DenArea',[
            e.text('DenUnavailable','Full Den publishing is unavailable: the service has no Den upload endpoint and the publishing/capture stage is pending. No Den data will be uploaded. Save your working Den as a new layout preset first; unsaved changes are never published.',12,e.DIM,wrap=True),
            e.entry_row('DenSaveRow',e.box('DenPresetName','New preset name'),e.button('SaveCommunityDen','Save current Den as NEW preset',14)),
            {'class':'/Script/UMG.SizeBox','name':'DenListSize','props':{'HeightOverride':'180','bOverride_HeightOverride':'true'},'children':[{'class':'/Script/UMG.ListView','name':'CommunityDenPresets','variable':True,'props':{'SelectionMode':'Single','EntryWidgetClass':e.ROOT+'WBP_DenCatalogShelf',**e.scrollbar()}}]},
            dict(e.button('PublishDenUnavailable','Publish full Den layout (unavailable)',14),props={**e.button('Unused','',14)['props'],'bIsEnabled':'false'}),
            e.text('CommunityDenSelected','Select a saved layout preset. Publishing remains unavailable.',12,e.DIM,wrap=True),
        ]),
        area('AccountArea',[
            e.text('CommunityProfile','Disconnected. Connect to check your Community profile.',12,e.DIM,wrap=True),
            e.entry_row('CommunityKeyRow',key,e.button('ConnectCommunity','Connect',14)),
            e.button('RememberCommunity','Remember connection: Off',14),
            e.row('AccountActions',[e.button('DisconnectCommunity','Disconnect',14),e.button('ForgetCommunity','Forget connection',14)]),
            e.text('CommunitySecurity','Remember connection saves the upload key locally as plain text. Anyone with that file can use it. Leave Off for this session only. Forget removes the saved key. The masked field clears on Connect and close. Keys pass through a temporary local transport file, removed after reading; do not include Community mailbox files or process dumps in diagnostics.',12,e.DIM,wrap=True),
            e.button('CommunityWebsite','Website account: Steam sign-in / generate key',14),
        ]),
        e.text('LibraryTitle','Saved local compositions · cached preview, name and part count',12,e.DIM,wrap=True),
        e.cards('CommunitySources'),
        e.button('CancelCommunity','Cancel transfer',14),
        e.text('Footer','',12,e.DIM,wrap=True),
    ])
    g.item('CommunityDenPresets','community_den_card');g.click('SaveCommunityDen','community_save_den')
    g.item('CommunitySources','community_source');g.item('CommunityListings','community_listing')
    g.click_with_text('FetchCommunity','community_fetch','CommunityCode');g.click('CancelCommunity','community_cancel')
    g.click('RememberCommunity','community_remember');g.click('ForgetCommunity','community_forget');g.click('ConnectCommunity','community_connect');g.click('DisconnectCommunity','community_disconnect');g.click('SubmitCommunity','community_submit')
    for button,event in [('CommunityBrowse','community_browse'),('CommunityUpload','community_upload'),('CommunityAccount','community_account'),('CommunityClose','community_close'),('BrowseCompositions','community_browse'),('BrowseDens','community_browse_dens'),('UploadComposition','community_upload'),('UploadDen','community_den'),('ReviewCommunity','community_review'),('CommunityWebsite','community_website'),('CopyCommunityURL','community_copy_url'),('CopyCommunityCode','community_copy_code')]:g.click(button,event)
    g.click_with_text('SearchCommunity','community_search','CommunitySearch');g.click('PreviousCommunity','community_previous');g.click('NextCommunity','community_next');g.click('RefreshCommunity','community_refresh');g.click('DownloadCommunity','community_download')
    return {'kind':'widget','path':e.ROOT+'WBP_DenCommunity','tree':tree,'functions':e.NATIVE_EVENT,'graph':g.spec()}
