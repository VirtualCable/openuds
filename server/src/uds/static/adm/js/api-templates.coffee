# jshint strict: true 

# -------------------------------
# Templates related
# Inserted into api
# for the admin app
# -------------------------------
"use strict"
@api = @api ? {}
$ = jQuery
api = @api

# Registers Handlebar useful helpers

# Iterate thought dictionary
Handlebars.registerHelper "eachKey", (context, options) ->
  ret = ""
  first = true
  for prop of context
    ret = ret + options.fn(
      key: prop
      value: context[prop]
      first: first
    )
    first = false
  ret


# Equal comparision (like if helper, but with comparation)
# Use as block as {{#ifequals [element] [element]}}....{{/ifequals}}
Handlebars.registerHelper "ifequals", (context1, context2, options) ->
  if String(context1) is String(context2)
    options.fn this
  else
    options.inverse this


# Belongs comparision (similar to "if xxx in yyyyy")
# Use as block as {{#ifbelong [element] [group]}}....{{/ifbelongs}}
Handlebars.registerHelper "ifbelongs", (context1, context2, options) ->
  gui.doLog "belongs", context1, context2
  unless $.inArray(context1, context2) is -1
    gui.doLog "belongs is true"
    options.fn this
  else
    options.inverse this


# Counters. 
# Create a counter with {{counter [id] [startValue]}}
# increment the counter with {{inc_counter [id]}}
# get the counter value tiwh {{get_counter [id}}
# Values are stored on current 
Handlebars.registerHelper "set_counter", (id, value, options) ->
  options.data["_counter_" + id] = value
  return

Handlebars.registerHelper "get_counter", (id, options) ->
  options.data["_counter_" + id]

Handlebars.registerHelper "inc_counter", (id, options) ->
  options.data["_counter_" + id] += 1
  return


# For inserting "inline" javascript scripts, due to the fact that we cannot
# Insert "<script>...</script>" inside inline elements (they are already scripts)
Handlebars.registerHelper "javascript", (options) ->
  new Handlebars.SafeString("<script>" + options.fn(this) + "</script>")


# Truncate chars, like django "truncatechars" filter
Handlebars.registerHelper "truncatechars", (len, value) ->
  val = value.toString() # For Array objects, the toString method joins the array and returns one string containing each array element separated by commas
  if val.length > len
    val.substring(0, len - 3) + "..."
  else
    val


# Remove white spaces
Handlebars.registerHelper "clean_whitespace", (value) ->
  val = value.toString() # For Array objects, the toString method joins the array and returns one string containing each array element separated by commas
  val.replace RegExp(" ", "g"), ""

api.templates = {}

# Now initialize templates api
api.templates.cache = new api.cache("tmpls") # Will cache templates locally. If name contains
# '?', data will not be cached and always
# re-requested. We do not care about lang, because page will reload on language change
api.templates.get = (name, success_fnc) ->
  $this = @
  success_fnc = success_fnc or ->

  api.doLog "Getting template " + name
  if name.indexOf("?") is -1
    if $this.cache.get(name + "------")
      success_fnc $this.cache.get(name)
      return
    
    # Let's check if a "preloaded template" exists                
    else if document.getElementById("tmpl_" + name)
      $this.cache.put name, "tmpl_" + name # In fact, this is not neccesary...
      success_fnc "tmpl_" + name
      return
  api.doLog "Invoking ajax for ", api.url_for(name, "template")
  $.ajax
    url: api.url_for(name, "template")
    type: "GET"
    dataType: "text"
    success: (data) ->
      cachedId = "tmpl_" + name
      $this.cache.put "_" + cachedId, $this.evaluate(data)
      $this.cache.put name, cachedId
      api.doLog "Success getting template \"" + name + "\"."
      success_fnc cachedId
      return

    fail: (jqXHR, textStatus, errorThrown) ->
      api.doLog jqXHR
      api.doLog textStatus
      apid.doLog errorThrown
      return

  return


# Simple JavaScript Templating, using HandleBars
api.templates.evaluate = (str, context) ->
  console.log "Evaluating ", str
  # Figure out if we're getting a template, or if we need to
  # load the template - and be sure to cache the result (compiled template).
  cached = null
  unless /\W/.test(str)
    console.log @cache
    cached = @cache.get("_" + str)
    if not cached?
      cached = api.templates.evaluate(document.getElementById(str).innerHTML)
      @cache.put "_" + str, cached
  template = cached or Handlebars.compile(str)
  (if context then template(context) else template)

return
