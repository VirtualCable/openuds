gui.gallery = new GuiElement(api.gallery, "imgal")
gui.gallery.link = ->
  "use strict"

  newImage = (meth, table, refreshFnc) ->
    api.templates.get "new_image", (tmpl) ->
      content = api.templates.evaluate(tmpl,
      )
      modalId = gui.launchModal(gettext("New image"), content,
        actionButton: "<button type=\"button\" class=\"btn btn-success button-accept\">" + gettext("Upload") + "</button>"
      )
      $(modalId + " .button-accept").click ->
        $(modalId).modal "hide"
        file = $('#id-image_for_gallery')[0].files[0]
        reader = new FileReader()

        reader.onload = (res) ->
          img = res.target.result
          img = img.substr img.indexOf("base64,") + 7
          data = {
            name: $('#id_image_name').val()
            data: img
          }
          api.gallery.put data, {
            success: refreshFnc
          }

        reader.readAsDataURL(file)

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
        "delete"
      ]
      onNew: newImage
      onDelete: gui.methods.del(gui.gallery, gettext("Delete Image"), gettext("Image deletion error"))
    return

  return