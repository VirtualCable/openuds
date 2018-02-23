/*global module:false*/
module.exports = function(grunt) {

  // Project configuration.
  grunt.initConfig({
    // Project settings
    config: {
      src: 'src',  // Src path
      dist: 'dist', // Dist path
      dev: 'dev'    // dev path
    },

    // Tasks
    clean: {
      dev: ['<%= config.dev %>'],
      dist: ['<%= config.dist %>'],
    },

    copy: {
      dev: {
        files: [
          { 
            expand: true, 
            flatten: true, 
            src: [
              'node_modules/bootstrap/dist/js/bootstrap.js',  // Bootstrap js
              'node_modules/jquery/dist/jquery.js',  // Jquery js
              'node_modules/popper.js/dist/popper.js' // Popper js
            ], 
            dest: '<%= config.dev %>/js/lib' 
          },  // To Lib folder
          { expand: true, flatten: true, src: ['<%= config.src %>/html/*.html'], dest:'<%= config.dev %>' }
        ]
      },
      dist: {
        files: [
          { 
            expand: true, 
            flatten: true, 
            src: [
              'node_modules/bootstrap/dist/js/bootstrap.min.js',  // Bootstrap js
              'node_modules/jquery/dist/jquery.min.js',  // Jquery js
              'node_modules/popper.js/dist/popper.min.js' // Popper js
            ], 
            dest: '<%= config.dist %>/js/lib' 
          },  // To Lib folder
          { expand: true, flatten: true, src: ['<%= config.src %>/html/*.html'], dest:'<%= config.dist %>' }
        ]
      }
    },

    coffee: {
      dev: {
        options: {
          sourceMap: true,
          join: true
        },
        files: {
          '<%= config.dev %>/js/uds.js': ['<%= config.src %>/js/*.coffee']
      },
      dist: {
        options: {
          sourceMap: false,
          join: true
        },
        files: {
          '<%= config.dist %>/js/uds.js': ['<%= config.src %>/js/*.coffee']
        }
      }
      }      
    },
    // Compiles Sass to CSS and generates necessary files if requested
    sass: {
      options: {
        trace: true,
        loadPath: [
          'node_modules/'
        ],
    },
      dev: {
        options: {
          update: true,
        },
        files: [{
          '<%= config.dev %>/css/uds.css': ['<%= config.src %>/css/uds.scss']
        }]
      },
      dist: {
        options: {
          update: false,
          style: 'compressed'
        },
        files: [{
          '<%= config.dist %>/css/uds.css': ['<%= config.src %>/css/uds.scss']
        }]
      }
    },

    /*watch: {
      gruntfile: {
        files: '<%= jshint.gruntfile.src %>',
        tasks: ['jshint:gruntfile']
      },
      lib_test: {
        files: '<%= jshint.lib_test.src %>',
        tasks: ['jshint:lib_test', 'qunit']
      }
    }*/
  });

  // These plugins provide necessary tasks.
  grunt.loadNpmTasks('grunt-contrib-sass');
  grunt.loadNpmTasks('grunt-contrib-coffee');
  grunt.loadNpmTasks('grunt-contrib-copy');
  grunt.loadNpmTasks('grunt-contrib-clean');

  // Default task.
  grunt.registerTask('dev', ['clean:dev', 'copy:dev', 'coffee:dev', 'sass:dev'])
  grunt.registerTask('default', ['dev']);

};
