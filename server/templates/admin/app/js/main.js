console.log('\'Allo \'Allo!'); // eslint-disable-line no-console
$(function(){
    var options = {
      //dom: '<"table-tbar btns-tables">frti',
      dom: '<"table-tbar btns-tables">fr<"uds-table"t>ip',
      responsive: true,
      colReorder: true,
      stateSave: true,
      paging: true,
      info: true,
      autoWidth: true,
      lengthChange: false,
      pageLength: 10,

      deferRender: true,
      paging: true,
      // pagingType: 'full',
      info: true,

      columnDefs: [ {
        orderable: false,
        className: 'select-checkbox',
        targets:   0
      } ],

      select: {
        style: 'os',
        items: 'row'
      },

      ordering: [[ 1, "asc" ]]

    }

    $('#table1').DataTable(options);
    $('#table2').DataTable(options);

    $('.table-tbar').html(
        '<div style="float: left;">' + 
        '  <div class="dropdown">' + 
        '    <button class="btn btn-action btn-tables dropdown-toggle" type="button" data-toggle="dropdown">' + 
        '      <span class="fa fa-pencil"></span> <span class="label-tbl-button">Nuevo</span>    <span class="caret"></span>' + 
        '    </button>' + 
        '    <ul class="dropdown-menu" role="menu" aria-labelledby="">' + 
        '        <li role="presentation"><a data-original-title="Proporciona conexión a los Servicios del Centro Virtual" role="menuitem" tabindex="-1" data-toggle="tooltip" title="" href="#" data-type="PhysicalMachinesServiceProvider"><span class="provi-PhysicalMachinesServiceProvider"></span> Physical Machines Provider</a></li>' + 
        '        <li role="presentation"><a data-original-title="Proveedor de servicios de muestra (y simulado)" role="menuitem" tabindex="-1" data-toggle="tooltip" title="" href="#" data-type="SampleProvider"><span class="provi-SampleProvider"></span> Proveedor de muestra</a></li>' + 
        '        <li role="presentation"><a data-original-title="Proveedor de servicios de plataforma HyperV (experimental)" role="menuitem" tabindex="-1" data-toggle="tooltip" title="" href="#" data-type="HyperVPlatform"><span class="provi-HyperVPlatform"></span> Proveedor de Plataforma HyperV (experimental)</a></li>' + 
        '        <li role="presentation"><a data-original-title="Proveedor de servicios de plataforma XenServer" role="menuitem" tabindex="-1" data-toggle="tooltip" title="" href="#" data-type="XenPlatform"><span class="provi-XenPlatform"></span> Proveedor de Plataforma XenServer</a></li>' + 
        '        <li role="presentation"><a data-original-title="Proveedor de servicios para la plataforma oVirt" role="menuitem" tabindex="-1" data-toggle="tooltip" title="" href="#" data-type="oVirtPlatform"><span class="provi-oVirtPlatform"></span> Proveedor de Plataformas oVirt/RHEV </a></li>' +
        '        <li role="presentation"><a data-original-title="Proveedor de servicios de prueba (y simulado)" role="menuitem" tabindex="-1" data-toggle="tooltip" title="" href="#" data-type="TestProvider"><span class="provi-TestProvider"></span> Proveedor de prueba</a></li>' + 
        '        <li role="presentation"><a data-original-title="Proveedor de Microsoft basado en RDS " role="menuitem" tabindex="-1" data-toggle="tooltip" title="" href="#" data-type="RDSProvider"><span class="provi-RDSProvider"></span> Proveedor de RDS (Experimental)</a></li>' + 
        '        <li role="presentation"><a data-original-title="Proporciona conexión a los Servicios del Centro Virtual" role="menuitem" tabindex="-1" data-toggle="tooltip" title="" href="#" data-type="VmwareVCServiceProvider"><span class="provi-VmwareVCServiceProvider"></span> Proveedor de VMWare Virtual Center </a></li>'+
        '        <li role="presentation"><a data-original-title="Proveedor Nutanix basado en MV" role="menuitem" tabindex="-1" data-toggle="tooltip" title="" href="#" data-type="NutanixProvider"><span class="provi-NutanixProvider"></span> Proveedor Nutanix Acrópolis (Experimental)</a></li>'+
        '    </ul>'+
        '  </div>'+
        '</div>'+
        '<button id="btn2265627877000671" class="btn btn-tables btn-action">'+
        '  <span class="fa fa-edit"></span> <span class="label-tbl-button">Editar</span>'+
        '</button>'+
        '<button id="btn7116895133755943" class="btn btn-tables btn-action">'+
        '  <div>Entrar en modo mantenimiento</div>'+
        '</button>' + 
        '<button id="btn9877117224970206" class="btn btn-tables btn-alert">'+
        '  <span class="fa fa-trash-o"></span> Borrar'+
        '</button>'+
        '<button id="btn06863313201655186" class="btn btn-tables btn-export disabled" disabled="true">'+
        '  <span class="fa fa-save"></span> <span class="label-tbl-button">Xls</span>'+
        '</button>'+
        '<button id="btn6091545362597098" class="btn btn-tables btn-action">'+
        '  <span class="fa fa-save"></span> <span class="label-tbl-button">Permisos</span>'+
        '</button>')
});
