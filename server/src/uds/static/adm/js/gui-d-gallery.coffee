gui.gallery = new GuiElement(api.gallery, "imgal")
gui.gallery.link = ->
  "use strict"
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
      onDelete: gui.methods.del(gui.gallery, gettext("Delete Image"), gettext("Image deletion error"))
    return

  return