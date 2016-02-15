console.log('\'Allo \'Allo!'); // eslint-disable-line no-console


// Sample services received
var services = [
  {
    name: 'Service1',
    group: 'Default',
    inuse: false,
    inmaintenance: false,
    transports: [
      {
        name: 'RDP',
        type: 'xxxx',
        id: 'a1234123123'
      }, 
      {
        name: 'RDP',
        type: 'xxxx',
        id: 'a1234123123'
      }
    ]
  },
]


function showTransports() {
    var $servicesGroup = $('#services-groups');

    alert($servicesGroup);

}