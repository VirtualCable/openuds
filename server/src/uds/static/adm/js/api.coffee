# jshint strict: true
"use strict"
@api = @api ? {}
$ = jQuery
api = @api

api.debug = off

api.permissions = {
  NONE: 0
  READ: 32
  MANAGEMENT: 64
  ALL: 96
}

api.doLog = (args...) ->
  if api.debug
    try
      args.push "API"
      console.log.apply window, args
  return

api.cacheTable = {}
api.cache = (cacheName) ->
  new Cache(cacheName)

api.cache.clear = (cacheName) ->
  if not cacheName?
    api.cacheTable = {}
  else
    api.cacheTable[cacheName] = {}
  return

api.url_for = (path, type='rest') ->
  api.doLog 'Url for: ', path, ', ', type
  switch type
    when "template"
      api.config.template_url + path
    when "rest"
      api.config.base_url + path
    else
      api.doLog 'Type of url not found: ' + type
      throw "Type of url not found: " + type

api.defaultFail = (jqXHR, textStatus, errorThrown) ->
  api.doLog jqXHR, ", ", textStatus, ", ", errorThrown
  return

api.getJson = (path, options) ->
  options = options or {}
  success_fnc = options.success or ->

  fail_fnc = options.fail or api.defaultFail
  url = api.url_for(path)
  api.doLog "Ajax GET Json for \"" + url + "\""
  $.ajax
    url: url
    type: options.method or "GET"
    dataType: "json"
    success: (data) ->
      api.doLog "Success on GET \"" + url + "\"."
      #api.doLog "Received ", data
      success_fnc data
      return

    error: (jqXHR, textStatus, errorThrown) ->
      api.doLog "Error on GET \"" + url + "\". ", textStatus, ", ", errorThrown
      fail_fnc jqXHR, textStatus, errorThrown
      return

    beforeSend: (request) ->
      request.setRequestHeader api.config.auth_header, api.config.token
      return

  return

api.putJson = (path, data, options) ->
  options = options or {}
  success_fnc = options.success or ->

  fail_fnc = options.fail or api.defaultFail
  url = api.url_for(path)
  api.doLog "Ajax PUT Json for \"" + url + "\""
  $.ajax
    url: url
    type: options.method or "PUT"
    dataType: "json"
    data: JSON.stringify(data)
    success: (data) ->
      api.doLog "Success on PUT \"" + url + "\"."
      # api.doLog "Received ", data
      success_fnc data
      return

    error: (jqXHR, textStatus, errorThrown) ->
      api.doLog "Error on PUT \"" + url + "\". ", textStatus, ", ", errorThrown
      fail_fnc jqXHR, textStatus, errorThrown
      return

    beforeSend: (request) ->
      request.setRequestHeader api.config.auth_header, api.config.token
      return

  return

api.deleteJson = (path, options) ->
  options = options or {}
  success_fnc = options.success or ->

  fail_fnc = options.fail or api.defaultFail
  url = api.url_for(path)
  api.doLog "Ajax DELETE Json for \"" + url + "\""
  $.ajax
    url: url
    type: "DELETE"
    dataType: "json"
    success: (data) ->
      api.doLog "Success on DELETE \"" + url + "\"."
      # api.doLog "Received ", data
      success_fnc data
      return

    error: (jqXHR, textStatus, errorThrown) ->
      api.doLog "Error on DELETE \"" + url + "\". ", textStatus, ", ", errorThrown
      fail_fnc jqXHR, textStatus, errorThrown
      return

    beforeSend: (request) ->
      request.setRequestHeader api.config.auth_header, api.config.token
      return

  return

class Cache
  constructor: (cacheName) ->
    api.cacheTable[cacheName] = api.cacheTable[cacheName] or {}
    @name = cacheName
    @cache = api.cacheTable[cacheName]

  get: (key, not_found_fnc) ->
    not_found_fnc = not_found_fnc or ->
      null

    @cache[key] = not_found_fnc()  if not @cache[key]?
    @cache[key] or undefined

  put: (key, value) ->
    @cache[key] = value
    return


class BasicModelRest
  constructor: (path, options) ->
    options = options or {}
    path = path or ""

    # Requests paths
    @path = path
    @getPath = options.getPath or path
    @logPath = options.logPath or path
    @putPath = options.putPath or path
    @testPath = options.testPath or (path + "/test")
    @delPath = options.delPath or path
    @typesPath = options.typesPath or (path + "/types")
    @guiPath = options.guiPath or (path + "/gui")
    @tableInfoPath = options.tableInfoPath or (path + "/tableinfo")
    @cache = api.cache("bmr" + path)

  _requestPath: (path, options) ->
    api.doLog "Requesting ", path, options
    options = options or {}
    success_fnc = options.success or ->
      api.doLog "success function not provided for " + path
      return

    fail_fnc = options.fail or (jqXHR, textStatus, errorThrown) ->
      api.doLog "failFnc not provided for " + path
      gui.tools.unblockUI()
      gui.notify 'Error ocurred: ' + textStatus, 'danger'

    cacheKey = options.cacheKey or path
    api.doLog 'CacheKey ', cacheKey
    if path is "."
      success_fnc {}
      return
    if cacheKey isnt "." and @cache.get(cacheKey)
      api.doLog "Cache SUCCESS for " + cacheKey
      success_fnc @cache.get(cacheKey)
    else
      api.doLog "Cache FAIL for " + cacheKey
      $this = @
      api.doLog 'Obtaining json for ', path
      api.getJson path,
        success: (data) ->
          $this.cache.put cacheKey, data  unless cacheKey is "."
          success_fnc data
          return

        fail: fail_fnc

    return

  get: (options) ->
    options = options or {}
    path = @getPath
    path += "/" + options.id  if options.id
    api.doLog "get Options: ", options, path
    @_requestPath path,
      cacheKey: "."
      success: options.success
      fail: options.fail


  list: (success_fnc, fail_fnc) ->
    @get
      id: ""
      success: success_fnc
      fail: fail_fnc


  overview: (success_fnc, fail_fnc) ->
    @get
      id: "overview"
      success: success_fnc
      fail: fail_fnc

  summary: (success_fnc, fail_fnc) ->
    @get
      id: "overview?summarize"
      success: success_fnc
      fail: fail_fnc


  item: (itemId, success_fnc, fail_fnc) ->
    @get
      id: itemId
      success: success_fnc
      fail: fail_fnc


  getLogs: (itemId, success_fnc, fail_fnc) ->
    path = @logPath + "/" + itemId + "/" + "log"
    @_requestPath path,
      cacheKey: "."
      success: success_fnc
      fail: fail_fnc


  put: (data, options) ->
    console.log("Data", data)
    options = options or {}
    path = @putPath
    path += "/" + options.id  if options.id
    api.putJson path, data,
      success: options.success
      fail: options.fail

    return

  create: (data, success_fnc, fail_fnc) ->
    @put data,
      success: success_fnc
      fail: fail_fnc


  save: (data, success_fnc, fail_fnc) ->
    @put data,
      id: data.id
      success: success_fnc
      fail: fail_fnc


  test: (type, data, success_fnc, fail_fnc) ->
    path = @testPath + "/" + type
    api.putJson path, data,
      success: success_fnc
      fail: fail_fnc
      method: "POST"

    return

  del: (id, success_fnc, fail_fnc) ->
    path = @delPath + "/" + id
    api.deleteJson path,
      success: success_fnc
      fail: fail_fnc

    return

  permission: () ->
    if api.config.admin is true
      return api.permissions.ALL

    return api.permissions.NONE

  getPermissions: (id, success_fnc, fail_fnc) ->
    path = "permissions/" + @path + '/' + id
    @_requestPath path,
      cacheKey: "."
      success: success_fnc
      fail: fail_fnc

  addPermission: (id, type, itemId, perm, success_fnc, fail_fnc) ->
    path = "permissions/" + @path + '/' + id + '/' + type + '/add/' + itemId
    data =
      perm: perm
    api.putJson path, data,
      success: success_fnc
      fail: fail_fnc

  revokePermissions: (itemIds, success_fnc, fail_fnc)->
    path = "permissions/revoke"
    data =
      items: itemIds
    api.putJson path, data,
      success: success_fnc
      fail: fail_fnc


  types: (success_fnc, fail_fnc) ->
    @_requestPath @typesPath,
      cacheKey: @typesPath
      success: success_fnc


  gui: (typeName, success_fnc, fail_fnc) ->
    path = null
    if typeName?
      path = [
        this.guiPath
        typeName
      ].join("/")
    else
      path = @guiPath

    @_requestPath path,
      cacheKey: '.'
      success: success_fnc
      fail: fail_fnc


  tableInfo: (success_fnc, fail_fnc) ->
    success_fnc = success_fnc or ->
      api.doLog "success not provided for tableInfo"
      return

    path = @tableInfoPath
    @_requestPath path,
      cacheKey: path
      success: success_fnc
      fail: fail_fnc

    return

  detail: (id, child, options) ->
    options = options or {}
    new DetailModelRestApi(this, id, child, options)

class DetailModelRestApi extends BasicModelRest
  constructor: (parentApi, parentId, model, options) ->
    super [
      parentApi.path
      parentId
      model
    ].join("/")
    @moptions = options

  permission: () ->
    if @moptions.permission? then @moptions.permission else api.permissions.ALL

  create: (data, success_fnc, fail_fnc) ->
    @put data,
      success: success_fnc
      fail: fail_fnc

  save: (data, success_fnc, fail_fnc) ->
    @put data,
      id: data.id
      success: success_fnc
      fail: fail_fnc

  types: (success_fnc, fail_fnc) ->
    if @moptions.types
      @moptions.types success_fnc, fail_fnc
    else
      super success_fnc, fail_fnc
    return

  # Generic "Invoke" method (with no args, if needed, put them on "method" after "?" as normal url would be
  invoke: (method, success_fnc, fail_fnc, options) ->
    options = options or {}
    meth = method
    if options.params
      meth += '?' + options.params
    @get
      id: meth
      success: success_fnc
      fail: fail_fnc

# Populate api
api.providers = new BasicModelRest("providers")

# all services method used in providers
api.providers.allServices = (success_fnc, fail_fnc) ->
  @get
    id: "allservices"
    success: success_fnc
    fail: fail_fnc


api.providers.service = (id, success_fnc, fail_fnc) ->
  @get
    id: "service/" + id
    success: success_fnc
    fail: fail_fnc

api.providers.maintenance = (id, success_fnc, fail_fnc) ->
  @get
    id: id + "/maintenance"
    success: success_fnc
    fail: fail_fnc

api.authenticators = new BasicModelRest("authenticators")

# Search method used in authenticators
api.authenticators.search = (id, type, term, success_fnc, fail_fnc) ->
  @get
    id: id + "/search?type=" + encodeURIComponent(type) + "&term=" + encodeURIComponent(term)
    success: success_fnc
    fail: fail_fnc


api.osmanagers = new BasicModelRest("osmanagers")
api.transports = new BasicModelRest("transports")
api.networks = new BasicModelRest("networks")

api.servicesPools = new BasicModelRest("servicespools")
api.servicesPools.setFallbackAccess = (id, fallbackAccess, success_fnc, fail_fnc) ->
  @get
    id: id + '/setFallbackAccess?fallbackAccess=' + fallbackAccess
    success: success_fnc
    fail: fail_fnc
api.servicesPools.actionsList = (id, success_fnc, fail_fnc) ->
  @get
    id: id + '/actionsList'
    success: success_fnc
    fail: fail_fnc

api.metaPools = new BasicModelRest("metapools")

api.configuration = new BasicModelRest("config")
api.gallery = new BasicModelRest("gallery/images")
api.sPoolGroups = new BasicModelRest("gallery/servicespoolgroups")
api.system = new BasicModelRest("system")
api.reports = new BasicModelRest("reports") # Not fully used, but basic usage is common
api.calendars = new BasicModelRest("calendars")

api.accounts = new BasicModelRest("accounts")
api.accounts.timemark = (id, success_fnc, fail_fnc) ->
  @get
    id: id + '/timemark'
    success: success_fnc
    fail: fail_fnc

api.proxies = new BasicModelRest("proxies")

# In fact, reports do not have any type
api.reports.types = (success_fnc, fail_fnc) ->
  success_fnc([])

api.system.stats = (type, success_fnc, fail_fnc) ->
  @get
    id: "stats/" + type
    success: success_fnc
    fail: fail_fnc


return
