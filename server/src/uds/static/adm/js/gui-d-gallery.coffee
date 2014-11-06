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
      gui.tools.applyCustoms modalId
      $(modalId + " .button-accept").click ->
        file = $('#id-image_for_gallery')[0].files[0]
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
          api.gallery.create data, refreshFnc

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