gui.gallery = new GuiElement(api.gallery, "imgal")
gui.gallery.link = ->
  "use strict"

  if api.config.admin is false
    return

  newEditImageFnc = (forEdit) ->
    realFnc = (value, refreshFnc) ->
      api.templates.get "new_image", (tmpl) ->
        content = api.templates.evaluate(tmpl,
        )
        modalId = gui.launchModal(gettext("New image"), content,
          actionButton: "<button type=\"button\" class=\"btn btn-success button-accept\">" + gettext("Upload") + "</button>"
        )
        gui.tools.applyCustoms modalId
        value is null or $("#id_image_name").val(value.name)
        $(modalId + " .button-accept").click ->
          file = $('#id-image_for_gallery')[0].files[0]

          if file is null
            gui.notify gettext("You must select an image")
            return

          name = $('#id_image_name').val()
          if name == ""
            name = file.name

          if file.size > 256*1024
            gui.notify gettext("Image is too big (max. upload size is 256Kb)")
            return

          $(modalId).modal "hide"
          reader = new FileReader()

          reader.onload = (res) ->
            img = res.target.result
            img = img.substr img.indexOf("base64,") + 7
            data = {
              data: img
              name: name
            }
            if value is null
              api.gallery.create data, refreshFnc
            else
              data.id = value.id
              api.gallery.save data, refreshFnc

          reader.readAsDataURL(file)
    if forEdit is true
      (value, event, table, refreshFnc) ->
        realFnc value, refreshFnc
    else
      (meth, table, refreshFnc) ->
        realFnc null, refreshFnc

  api.templates.get "gallery", (tmpl) ->
    gui.clearWorkspace()
    gui.appendToWorkspace api.templates.evaluate(tmpl,
      gallery: "gallery-placeholder"
    )
    gui.gallery.table
      container: "gallery-placeholder"
      rowSelect: "single"
      buttons: [
        "new"
        "edit"
        "delete"
      ]
      onNew: newEditImageFnc false
      onEdit: newEditImageFnc true
      onDelete: gui.methods.del(gui.gallery, gettext("Delete Image"), gettext("Image deletion error"))
    return

  return