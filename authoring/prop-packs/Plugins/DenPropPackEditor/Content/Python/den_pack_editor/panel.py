"""Dockable UMG panel. All callbacks run in Unreal's editor Python interpreter."""
import copy
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import subprocess
import sys
import traceback
import unreal as u
from . import model, service

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix='DenPackExport')
_current = None


def reveal(path):
    if sys.platform=='win32': os.startfile(str(path))
    else: subprocess.Popen(['xdg-open',str(path)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)


class Panel:
    def __init__(self, widget):
        self.widget=widget
        self.root=widget.find_child_widget_by_name('CanvasPanel_0')
        if self.root is None: raise RuntimeError('Missing prop-pack panel root')
        self.outer=self.root.get_outer()
        self.doc=model.blank();self.baseline=copy.deepcopy(self.doc);self.folder=None
        self.rows=[];self.fields={};self.buttons=[];self.future=None;self.output='';self.job=None;self.tick=None
        self.root.clear_children()
        background=self.new(u.Border)
        background.set_brush_color(u.LinearColor(0.035,0.045,0.06,1))
        background.set_padding(u.Margin(18,18,18,18))
        slot=self.root.add_child_to_canvas(background)
        slot.set_anchors(u.Anchors(u.Vector2D(0,0),u.Vector2D(1,1)));slot.set_offsets(u.Margin(0,0,0,0))
        body=self.new(u.VerticalBox);background.add_child(body)
        self.text(body,'Den Designer · Prop packs',24)
        self.text(body,'Create a pack, import meshes into its content folder, then add them below.',12)
        bar=self.new(u.HorizontalBox);body.add_child(bar)
        self.button(bar,'New pack',self.new_pack)
        chooser=self.new(u.SizeBox);chooser.set_width_override(180)
        chooser_slot=bar.add_child(chooser);chooser_slot.set_padding(u.Margin(0,5,8,5))
        self.packs=self.new(u.ComboBoxString);chooser.add_child(self.packs)
        pack_font=self.packs.get_editor_property('font');pack_font.size=12
        self.packs.set_editor_property('font',pack_font)
        self.button(bar,'Refresh',self.refresh_packs)
        self.button(bar,'Open pack',self.open_pack)
        self.button(bar,'Save pack',self.save_pack)
        self.button(bar,'Show content',self.show_content)
        self.form=self.new(u.VerticalBox);body.add_child(self.form)
        for name,label in [('plugin','Plugin name'),('id','Permanent pack ID'),('title','Title'),('author','Author'),('version','Version'),('nexus_url','Nexus page (optional)')]:
            row=self.new(u.HorizontalBox);self.form.add_child(row)
            self.label(row,label,155)
            field=self.edit(row,'',None)
            self.fields[name]=field
        bar=self.new(u.HorizontalBox);body.add_child(bar)
        self.button(bar,'Add selected meshes',self.add_selected)
        self.button(bar,'Validate',self.validate_pack)
        self.button(bar,'Build pack',self.start_build)
        self.text(body,'Props · name, tags, description and dimensions in centimetres',14)
        self.scroll=self.new(u.ScrollBox)
        slot=body.add_child(self.scroll);slot.set_size(u.SlateChildSize(value=1.0,size_rule=u.SlateSizeRule.FILL))
        self.status=self.text(body,'Save a new pack to create its content folder. Plugin name and pack ID stay fixed after creation.',12)
        self.status.set_auto_wrap_text(True)
        footer=self.new(u.HorizontalBox);body.add_child(footer)
        self.export_button=self.button(footer,'Open export folder',lambda:reveal(self.output))
        self.logs_button=self.button(footer,'Open build logs',lambda:reveal(self.job['output']))
        self.export_button.set_is_enabled(False);self.logs_button.set_is_enabled(False)
        self.fixed_buttons=list(self.buttons)
        self.refresh_packs();self.render()

    def new(self,cls):
        return u.new_object(cls,outer=self.outer)

    def text(self,parent,value,size=12):
        obj=self.new(u.TextBlock);obj.set_text(str(value))
        font=obj.get_editor_property('font');font.size=size;obj.set_font(font)
        obj.set_color_and_opacity(u.SlateColor(specified_color=u.LinearColor(0.88,0.90,0.94,1)))
        slot=parent.add_child(obj)
        if hasattr(slot,'set_padding'):slot.set_padding(u.Margin(0,5,8,5))
        return obj

    def label(self,parent,value,width):
        box=self.new(u.SizeBox);box.set_width_override(width);parent.add_child(box)
        return self.text(box,value)

    def edit(self,parent,value,width):
        box=self.new(u.SizeBox)
        if width:box.set_width_override(width)
        slot=parent.add_child(box)
        if width is None and hasattr(slot,'set_size'):slot.set_size(u.SlateChildSize(value=1.0,size_rule=u.SlateSizeRule.FILL))
        if hasattr(slot,'set_padding'):slot.set_padding(u.Margin(0,3,8,3))
        edit=self.new(u.EditableTextBox);edit.set_text(str(value));box.add_child(edit)
        return edit

    def button(self,parent,label,callback):
        button=self.new(u.Button);slot=parent.add_child(button)
        if hasattr(slot,'set_padding'):slot.set_padding(u.Margin(0,5,8,5))
        self.text(button,label)
        button.on_clicked.add_callable(lambda:self.guard(callback))
        self.buttons.append(button)
        return button

    def guard(self,callback):
        try:callback()
        except Exception as exc:
            self.message(str(exc));u.log_error('Den Prop Packs: '+traceback.format_exc())

    def message(self,text):self.status.set_text(str(text))

    def refresh_packs(self):
        selected=self.packs.get_selected_option()
        self.packs.clear_options()
        for name in service.list_packs():self.packs.add_option(name)
        if selected:self.packs.set_selected_option(selected)

    def collect(self):
        result=copy.deepcopy(self.doc)
        for name,field in self.fields.items():result[name]=str(field.get_text())
        if not result.get('nexus_url'):result.pop('nexus_url',None)
        result['props']=[]
        for original,fields in self.rows:
            row=copy.deepcopy(original)
            for key in ('name','tags','description'):row[key]=str(fields[key].get_text())
            row['size']=[fields[k].get_value() for k in ('x','y','z')]
            row['collision']=fields['collision'].is_checked()
            result['props'].append(row)
        return result

    def confirm_switch(self):
        if self.collect()==self.baseline:return True
        return u.EditorDialog.show_message('Unsaved pack metadata','Switch packs and discard unsaved metadata changes? Imported assets are unaffected.',u.AppMsgType.YES_NO)==u.AppReturnType.YES

    def new_pack(self):
        if not self.confirm_switch():return
        self.doc=model.blank();self.baseline=copy.deepcopy(self.doc);self.folder=None
        self.render();self.message('Enter the pack details, then Save pack to create its content folder.')

    def open_pack(self):
        name=self.packs.get_selected_option()
        if not name:raise ValueError('Choose a pack from the list first')
        doc,folder=service.open_pack(name)
        if not self.confirm_switch():return
        self.doc=doc;self.baseline=copy.deepcopy(doc);self.folder=folder
        self.render();self.message('Opened '+doc['title'])

    def save_pack(self):
        doc=self.collect()
        self.folder=service.save(doc,self.folder)
        self.doc=doc;self.baseline=copy.deepcopy(doc)
        self.fields['plugin'].set_is_read_only(True);self.fields['id'].set_is_read_only(True)
        self.refresh_packs();self.packs.set_selected_option(doc['plugin'])
        self.message(('Saved. Import meshes into /'+doc['plugin']+'/, then select them and choose Add selected meshes.') if service.mount(doc,self.folder) else 'Pack saved. Restart the editor once to mount the new content folder, then reopen this pack.')

    def show_content(self):
        if not self.folder:raise ValueError('Save a new pack first')
        service.require_mount(self.doc,self.folder)
        u.EditorUtilityLibrary.sync_browser_to_folders(['/'+self.doc['plugin']])

    def add_selected(self):
        if not self.folder:raise ValueError('Save a new pack first')
        self.doc=self.collect()
        service.require_mount(self.doc,self.folder)
        added,skipped=service.add_meshes(self.doc)
        self.render();self.message(f'Added {added} meshes; skipped {skipped} duplicates, non-mesh assets or assets outside this pack. Save pack to keep changes.')

    def remove(self,index):
        self.doc=self.collect();self.doc['props'].pop(index);self.render()
        self.message('Removed this registration entry. The imported asset is still in the Content Browser.')

    def render(self):
        for name,field in self.fields.items():field.set_text(self.doc.get(name,''))
        for name in ('plugin','id'):self.fields[name].set_is_read_only(self.folder is not None)
        self.scroll.clear_children();self.rows=[]
        # Row buttons disappear with their rows; keep only controls in the fixed form.
        self.buttons=list(self.fixed_buttons)
        if not self.doc['props']:
            self.text(self.scroll,'No props yet. Select meshes in this pack’s Content Browser folder and add them.',13)
        for i,prop in enumerate(self.doc['props']):
            border=self.new(u.Border);border.set_padding(u.Margin(10,8,10,8));border.set_brush_color(u.LinearColor(.06,.075,.095,1))
            self.scroll.add_child(border)
            group=self.new(u.VerticalBox);border.add_child(group)
            self.text(group,prop['mesh'],10)
            row=self.new(u.HorizontalBox);group.add_child(row)
            self.label(row,'Name',65);fields={'name':self.edit(row,prop['name'],None)}
            self.button(row,'Remove',lambda index=i:self.remove(index))
            row=self.new(u.HorizontalBox);group.add_child(row)
            self.label(row,'Tags',65);fields['tags']=self.edit(row,prop.get('tags',''),None)
            row=self.new(u.HorizontalBox);group.add_child(row)
            self.label(row,'Details',65);fields['description']=self.edit(row,prop.get('description',''),None)
            row=self.new(u.HorizontalBox);group.add_child(row)
            for axis,value in zip(('x','y','z'),prop['size']):
                self.label(row,axis.upper(),25)
                box=self.new(u.SizeBox);box.set_width_override(90);row.add_child(box)
                spin=self.new(u.SpinBox);spin.set_min_value(0);spin.set_max_value(100000);spin.set_value(value);box.add_child(spin);fields[axis]=spin
            self.label(row,'Solid',55);check=self.new(u.CheckBox);check.set_is_checked(prop['collision']);row.add_child(check);fields['collision']=check
            self.rows.append((prop,fields))

    def validate_pack(self):
        warnings=service.validate(self.collect())
        text='Validation passed.'
        if warnings:text+='\n'+'\n'.join(warnings)
        if sys.platform!='win32':text+='\nLinux exports still need an in-game check; custom Windows shaders require a Windows cook.'
        self.message(text)

    def busy(self,value):
        self.form.set_is_enabled(not value);self.scroll.set_is_enabled(not value);self.packs.set_is_enabled(not value)
        for button in self.buttons:button.set_is_enabled(not value)
        self.export_button.set_is_enabled(not value and bool(self.output))
        self.logs_button.set_is_enabled(bool(self.job))

    def start_build(self):
        if self.future is not None:return
        doc=self.collect()
        service.validate(doc)
        self.folder=service.save(doc,self.folder)
        self.doc=doc;self.baseline=copy.deepcopy(doc)
        self.job=service.prepare_build(doc,self.folder)
        self.render();self.refresh_packs();self.packs.set_selected_option(doc['plugin'])
        self.output='';self.busy(True)
        self.message('Cooking pack… The editor remains usable. Open build logs for details.')
        self.future=_executor.submit(service.build,self.job)
        self.tick=u.register_slate_post_tick_callback(self.poll_build)

    def poll_build(self,delta):
        if self.future is None or not self.future.done():return
        future=self.future;self.future=None
        if self.tick is not None:u.unregister_slate_post_tick_callback(self.tick);self.tick=None
        try:
            self.output=future.result()
            self.message('Export complete. Test the pack in game before sharing.\n'+self.output)
        except Exception as exc:self.message('Build failed. No export was published.\n'+str(exc))
        self.busy(False)


def open_panel():
    global _current
    bp=u.load_asset('/DenPropPackEditor/UI/EUW_PropPacks')
    if bp is None:raise RuntimeError('Prop-pack panel asset is missing. Reinstall the complete authoring bundle.')
    widget=u.get_editor_subsystem(u.EditorUtilitySubsystem).spawn_and_register_tab(bp)
    if _current is None:
        _current=Panel(widget)
    elif _current.widget!=widget:
        old=_current
        # The old controller stays alive through its tick callback while cooking.
        # Reattach its state to the new tab without starting a second build.
        fresh=Panel(widget)
        fresh.doc=old.collect();fresh.baseline=old.baseline;fresh.folder=old.folder
        fresh.job=old.job;fresh.output=old.output;fresh.future=old.future
        fresh.render();fresh.message(str(old.status.get_text()))
        if fresh.folder:fresh.packs.set_selected_option(fresh.doc['plugin'])
        if old.tick is not None:
            u.unregister_slate_post_tick_callback(old.tick);old.tick=None
        old.future=None
        if fresh.future is not None:
            fresh.tick=u.register_slate_post_tick_callback(fresh.poll_build)
        fresh.busy(fresh.future is not None)
        _current=fresh
    return _current
