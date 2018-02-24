/*global module:false*/
module.exports = function(grunt) {

  // Project configuration.
  grunt.initConfig({
    // Project settings
    config: {
      dist: 'dist', // Dist path
      dev: 'dev',    // dev path
      // Source elements path
      src: {
        html: 'src/index.html',
        templates: 'src/templates/*.html',
        sass: 'src/css/uds.scss', 
        sass_watch: 'src/css/**/*.scss', 
        coffee: 'src/js/**/*.coffee'
      }
      
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
              'node_modules/popper.js/dist/popper.js', // Popper js
              'node_modules/angular/angular.js' // Angular
            ], 
            dest: '<%= config.dev %>/js/lib' 
          },  // To Lib folder
          // Index & Templates
          { expand: true, flatten: true, src: ['<%= config.src.html %>'], dest:'<%= config.dev %>' },
          { expand: true, flatten: true, src: ['<%= config.src.templates %>'], dest:'<%= config.dev %>/templates' },
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
          },
          // Index & Templates
          { expand: true, flatten: true, src: ['<%= config.src.html %>'], dest:'<%= config.dist %>' },
          { expand: true, flatten: true, src: ['<%= config.src.templates %>'], dest:'<%= config.dist %>/templates' },
          
        ]
      }
    },

    coffee: {
      options: {
        join: true,
      },
      dev: {
        options: {
          sourceMap: true,
        },
        files: {
          '<%= config.dev %>/js/uds.js': ['<%= config.src.coffee %>']
        },
      },
      dist: {
        options: {
          sourceMap: false,
        },
        files: {
          '<%= config.dist %>/js/uds.js': ['<%= config.src.coffee %>']
        },
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
          '<%= config.dev %>/css/uds.css': ['<%= config.src.sass %>']
        }]
      },
      dist: {
        options: {
          update: false,
          style: 'compressed'
        },
        files: [{
          '<%= config.dist %>/css/uds.css': ['<%= config.src.sass %>'],
        }]
      }
    },

    watch: {
      typescript: {
        files: '<%= config.src.typescript %>',
        tasks: ['typescrypt:dev']
      },
      sass: {
        files: '<%= config.src.sass_watch %>',
        tasks: ['sass:dev']
      },
      html: {
        files: '<%= config.src.html %>',
        tasks: ['copy:dev']
      }
    },
    'http-server': {
      dev: {
        root: '<%= config.dev %>',
        port: 9000,
        host: '0.0.0.0',
        cache: 0
      }
    }
  
  });

  // These plugins provide necessary tasks.
  grunt.loadNpmTasks('grunt-contrib-sass');
  grunt.loadNpmTasks('grunt-contrib-copy');
  grunt.loadNpmTasks('grunt-contrib-clean');
  grunt.loadNpmTasks('grunt-contrib-watch');
  grunt.loadNpmTasks('grunt-http-server');
  grunt.loadNpmTasks('grunt-contrib-coffee');

  // Default task.
  grunt.registerTask('dev', ['copy:dev', 'coffee:dev', 'sass:dev'])
  grunt.registerTask('dist', ['clean:dist', 'copy:dist', 'coffee:dist', 'sass:dist'])
  grunt.registerTask('default', ['dev']);

};
